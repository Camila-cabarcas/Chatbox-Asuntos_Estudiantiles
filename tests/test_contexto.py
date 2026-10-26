"""Contexto para el modelo: secciones completas, sin duplicados y con presupuesto."""

from app.rag.contexto import armar_contexto
from app.rag.fichas import Seccion
from app.rag.indice import Resultado
from app.rag.tokens import estimar_tokens


def seccion(ficha_id: str, i: int, largo: int = 20) -> Seccion:
    return Seccion(id=f"{ficha_id}::{i}", ficha_id=ficha_id, titulo=ficha_id.upper(),
                   nombre=f"Sección {i}", url=f"https://{ficha_id}", cuerpo="x" * largo)


class Fuente:
    def __init__(self, secciones: list[Seccion]):
        self._s = {s.id: s for s in secciones}

    def seccion(self, seccion_id):
        return self._s.get(seccion_id)

    def secciones_de_ficha(self, ficha_id):
        return [s for s in self._s.values() if s.ficha_id == ficha_id]


def resultado(ficha_id: str, tipo: str, seccion_id: str = "", id_: str = "", texto: str = "frag"):
    return Resultado(texto=texto, ficha_id=ficha_id, titulo=ficha_id.upper(), seccion="",
                     url=f"https://{ficha_id}", distancia=0.1, id=id_ or f"{ficha_id}-{seccion_id}",
                     tipo=tipo, seccion_id=seccion_id)


FUENTE = Fuente([seccion("a", 0), seccion("a", 1), seccion("a", 2), seccion("b", 0), seccion("b", 1)])


def texto(seccion_id: str) -> str:
    return FUENTE._s[seccion_id].texto


def test_acierto_en_seccion_trae_la_seccion_completa():
    partes = armar_contexto([resultado("b", "seccion", "b::1")], FUENTE, 1500)
    assert partes == [texto("b::1")]


def test_acierto_en_pregunta_trae_las_secciones_de_la_ficha():
    partes = armar_contexto([resultado("a", "pregunta")], FUENTE, 1500)
    assert partes == [s.texto for s in FUENTE.secciones_de_ficha("a")]


def test_sin_duplicados():
    rs = [resultado("a", "seccion", "a::1", id_="a1.0"), resultado("a", "seccion", "a::1", id_="a1.1"),
          resultado("a", "pregunta")]
    partes = armar_contexto(rs, FUENTE, 1500)
    assert len(partes) == len(set(partes)) == 3


def test_pasada_de_variedad_incluye_varias_fichas_antes_de_rellenar():
    rs = [resultado("a", "pregunta"), resultado("b", "pregunta")]
    partes = armar_contexto(rs, FUENTE, 1500)
    assert partes[:2] == [texto("a::0"), texto("b::0")]
    assert set(partes) == {s.texto for s in FUENTE._s.values()}


def test_respeta_el_presupuesto():
    una = estimar_tokens(texto("a::0"))
    partes = armar_contexto([resultado("a", "pregunta"), resultado("b", "pregunta")], FUENTE, 2 * una)
    assert len(partes) == 2
    assert sum(estimar_tokens(p) for p in partes) <= 2 * una


def test_si_la_seccion_no_cabe_usa_el_fragmento_encontrado():
    grande = Fuente([seccion("c", 0, largo=5000)])
    partes = armar_contexto([resultado("c", "seccion", "c::0", texto="fragmento chico")], grande, 300)
    assert partes == ["fragmento chico"]


def test_indice_antiguo_sin_seccion_id_usa_el_fragmento():
    partes = armar_contexto([resultado("z", "seccion", "", texto="texto del fragmento")], FUENTE, 1500)
    assert partes == ["texto del fragmento"]
