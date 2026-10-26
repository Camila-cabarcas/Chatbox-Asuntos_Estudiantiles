"""
Troceado de las fichas en fragmentos de búsqueda que caben en el límite
del modelo de embeddings. No requieren el modelo: usan el contador del modo
mock o uno por palabras. La única prueba con el tokenizador real se salta
sola si el modelo no está descargado.
"""

import logging

import pytest

from app.config import RAIZ_PROYECTO
from app.rag.fichas import (
    SECCION_PREGUNTAS, _FIN_DE_FRASE, Ficha, cargar_fichas, cargar_fragmentos,
    dividir, secciones_de,
)
from app.rag.tokens import estimar_tokens

FICHAS = RAIZ_PROYECTO / "fichas"
MODELO_REAL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def por_palabras(texto: str) -> int:
    return len(texto.split()) + 2


def ficha(cuerpo: str, preguntas: list[str] | None = None) -> Ficha:
    return Ficha(id="f", titulo="Trámite", url="https://x", cuerpo=cuerpo,
                 preguntas_ejemplo=preguntas or [])


def cuerpo_sin_cabecera(texto: str) -> str:
    return texto.split("\n", 2)[2]


def es_una_sola_frase(texto: str) -> bool:
    cuerpo = cuerpo_sin_cabecera(texto)
    return "\n" not in cuerpo and len(_FIN_DE_FRASE.split(cuerpo)) == 1


@pytest.mark.parametrize("contar,limite", [(estimar_tokens, 128), (por_palabras, 40)])
def test_solo_supera_el_limite_una_frase_que_no_se_puede_dividir(contar, limite):
    fragmentos = cargar_fragmentos(FICHAS, contar=contar, limite=limite, avisar=False)
    assert fragmentos
    excedidos = [f for f in fragmentos if contar(f.texto) > limite]
    assert all(es_una_sola_frase(f.texto) for f in excedidos), [f.id for f in excedidos]
    # Con el límite realista casi todo cabe; si muchos se pasan, algo falla.
    if limite == 128:
        assert len(excedidos) <= 0.05 * len(fragmentos)


def test_cada_pregunta_de_ejemplo_es_un_fragmento_propio():
    fichas = cargar_fichas(FICHAS)
    preguntas = [f for f in cargar_fragmentos(FICHAS) if f.tipo == "pregunta"]
    esperadas = {f"{fi.titulo}\n{SECCION_PREGUNTAS}\n{p}" for fi in fichas for p in fi.preguntas_ejemplo}
    assert len(preguntas) == sum(len(fi.preguntas_ejemplo) for fi in fichas)
    assert {f.texto for f in preguntas} == esperadas
    assert all(f.seccion_id == "" for f in preguntas)


def test_fragmentos_empiezan_con_titulo_y_seccion_y_no_parten_frases():
    for fi in cargar_fichas(FICHAS):
        fragmentos = dividir(fi, contar=por_palabras, limite=40, avisar=False)
        for s in secciones_de(fi):
            propios = [f.texto for f in fragmentos if f.seccion_id == s.id]
            assert propios, s.id
            assert all(t.startswith(f"{fi.titulo}\n{s.nombre}\n") for t in propios)
            for linea in s.cuerpo.splitlines():
                for frase in _FIN_DE_FRASE.split(linea.strip()):
                    if frase:
                        assert any(frase in t for t in propios), (s.id, frase)


def test_linea_madre_encabeza_las_partes_de_un_elemento_dividido():
    hijas = "\n".join(f"   - Requisito número {i} con varias palabras de relleno" for i in range(8))
    fr = dividir(ficha(f"## Reglas\n1. **Materias del núcleo común**:\n{hijas}"),
                 contar=por_palabras, limite=30)
    assert len(fr) > 1
    assert all(cuerpo_sin_cabecera(f.texto).startswith("1. **Materias del núcleo común**:") for f in fr)


def test_partes_consecutivas_comparten_solapamiento():
    parrafos = [f"Párrafo {i} " + "palabra " * 8 for i in range(6)]
    cuerpo = "## Sección\n" + "\n\n".join(p.strip() for p in parrafos)
    con = dividir(ficha(cuerpo), contar=por_palabras, limite=30, solapamiento=1)
    sin = dividir(ficha(cuerpo), contar=por_palabras, limite=30, solapamiento=0)
    assert len(con) > 2
    for a, b in zip(con, con[1:]):
        assert cuerpo_sin_cabecera(a.texto).split("\n")[-1] == cuerpo_sin_cabecera(b.texto).split("\n")[0]
    for a, b in zip(sin, sin[1:]):
        assert set(cuerpo_sin_cabecera(a.texto).split("\n")).isdisjoint(cuerpo_sin_cabecera(b.texto).split("\n"))


def test_una_introduccion_no_queda_al_final_de_una_parte():
    cuerpo = ("## Notas\n" + "Primer párrafo " + "texto " * 15 + "\n\n"
              "**Regla de cancelación por tercera vez**:\n\n" + "Contenido de la regla " + "texto " * 15)
    fr = dividir(ficha(cuerpo), contar=por_palabras, limite=30, solapamiento=0)
    assert not any(f.texto.rstrip().endswith(":") for f in fr)
    assert any("**Regla de cancelación por tercera vez**:\nContenido" in f.texto for f in fr)


def test_frase_mas_larga_que_el_limite_se_deja_entera_y_avisa(caplog):
    frase = "Una sola frase " + "muy " * 60 + "larga sin puntos intermedios"
    with caplog.at_level(logging.WARNING):
        fr = dividir(ficha(f"## Sección\n{frase}"), contar=por_palabras, limite=30)
    assert len(fr) == 1 and frase in fr[0].texto
    assert "supera el límite" in caplog.text


def test_separadores_no_son_contenido():
    s = secciones_de(ficha("## A\nTexto uno.\n\n---\n\nTexto dos."))[0]
    assert "---" not in s.cuerpo and "Texto uno." in s.cuerpo and "Texto dos." in s.cuerpo


def test_con_tokenizador_real_ningun_fragmento_supera_el_modelo():
    st = pytest.importorskip("sentence_transformers")
    try:
        modelo = st.SentenceTransformer(MODELO_REAL, local_files_only=True)
    except Exception as e:  # modelo no descargado: no se descarga en las pruebas
        pytest.skip(f"Modelo {MODELO_REAL} no disponible sin conexión ({type(e).__name__})")
    limite = modelo.max_seq_length

    def contar(t: str) -> int:
        return len(modelo.tokenizer(t, verbose=False)["input_ids"])

    fragmentos = cargar_fragmentos(FICHAS, contar=contar, limite=limite)
    excedidos = [(f.id, contar(f.texto)) for f in fragmentos if contar(f.texto) > limite]
    assert not excedidos
