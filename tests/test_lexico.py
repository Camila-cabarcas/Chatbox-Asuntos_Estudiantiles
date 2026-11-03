"""Ranking léxico (BM25) que complementa la búsqueda vectorial.

El vectorial es el que decide si la pregunta es del dominio; el léxico solo
propone fichas adicionales cuando el modelo ya respondió "no encontré".
"""

from types import SimpleNamespace

import pytest

from app.rag.indice import IndiceVectorial
from app.rag.lexico import IndiceLexico, normalizar, palabras

DOCS = [
    ("pasos-para-radicar", "Pasos para radicar en SSOFI: configura los desplegables "
                           "y adjunta la documentación en un solo PDF."),
    ("pasos-para-radicar", "Pasos para radicar en SSOFI: ingresa el código y envía "
                           "la solicitud al comité."),
    ("reconocimiento-homologacion-materias",
     "Reconocimiento y homologación: refrendar asignaturas aprobadas en otra "
     "institución con certificado de calificaciones."),
]


def indice(hibrido: bool = True, margen: float = 0.65) -> IndiceVectorial:
    """IndiceVectorial con el léxico ya armado (sin Chroma ni embeddings)."""
    idx = object.__new__(IndiceVectorial)
    idx._settings = SimpleNamespace(rag_hibrido=hibrido, rag_hibrido_margen=margen)
    idx._lexico = IndiceLexico(
        textos=[t for _, t in DOCS], fichas=[f for f, _ in DOCS])
    return idx


# --- Normalización ---------------------------------------------------------

def test_palabras_quita_vacias_tildes_y_palabras_cortas():
    assert palabras("¿REFRENDAR una materia de la U?") == ["refrendar", "materia"]


def test_normalizar_conserva_letras_y_quita_tildes():
    assert normalizar("Homologación") == "homologacion"


# --- BM25 -----------------------------------------------------------------

def test_premia_el_termino_poco_frecuente():
    puntajes = IndiceLexico(**{"textos": [t for _, t in DOCS],
                               "fichas": [f for f, _ in DOCS]}).puntuar(
        "quiero refrendar lo aprobado en otra institución")
    ranking = sorted(puntajes, key=puntajes.get, reverse=True)
    assert ranking[0] == "reconocimiento-homologacion-materias"
    # "pasos" aparece en dos fichas: no puede ganarle a "refrendar".
    assert puntajes["reconocimiento-homologacion-materias"] > max(
        puntajes.get("pasos-para-radicar", 0.0), 0.0)


def test_puntaje_es_el_del_mejor_fragmento_no_la_suma():
    # "repartida" tiene los cuatro términos, pero en dos fragmentos distintos;
    # "junta" los tiene todos en un solo fragmento. Si se sumaran los dos
    # fragmentos de "repartida", ganaría ella: debe ganar "junta".
    corpus = IndiceLexico(
        textos=["refrendar materia", "certificado institución",
                "refrendar materia certificado institución"],
        fichas=["repartida", "repartida", "junta"]).puntuar(
        "refrendar materia certificado institución")
    assert corpus["junta"] > corpus["repartida"]


def test_consulta_sin_terminos_conocidos_no_puntua():
    assert IndiceLexico(["texto cualquiera"], ["a"]).puntuar("zzz qqq") == {}


def test_textos_y_fichas_deben_cuadrar():
    with pytest.raises(ValueError):
        IndiceLexico(["uno", "dos"], ["solo-una"])


# --- Rescate (fichas_lexicas) ---------------------------------------------

def test_sin_hibrido_no_rescata_nada():
    assert indice(hibrido=False).fichas_lexicas(
        "refrendar institución", ya_elegidas=["pasos-para-radicar"]) == []


def test_descarta_la_ficha_que_el_vectorial_ya_trajo():
    propuestas = indice(margen=0.0).fichas_lexicas(
        "refrendar homologación asignaturas institución",
        ya_elegidas=["reconocimiento-homologacion-materias"])
    assert "reconocimiento-homologacion-materias" not in propuestas


def test_margen_descarta_la_ficha_que_puntua_mucho_peor():
    pregunta = "refrendar homologación asignaturas institución documentación"
    # "pasos-para-radicar" solo comparte "documentación": queda muy por debajo
    # de la ficha que el vectorial ya eligió.
    assert indice(margen=0.65).fichas_lexicas(
        pregunta, ya_elegidas=["reconocimiento-homologacion-materias"]) == []
    # Con el margen apagado sí entra: así se comprueba que el descarte es del
    # margen y no de que el léxico no la haya encontrado.
    assert indice(margen=0.0).fichas_lexicas(
        pregunta, ya_elegidas=["reconocimiento-homologacion-materias"])


def test_como_maximo_dos_fichas():
    idx = indice(margen=0.0)
    propuestas = idx.fichas_lexicas(
        "refrendar pasos SSOFI adjunta documentación aprobadas",
        ya_elegidas=[])
    assert 0 < len(propuestas) <= 2
