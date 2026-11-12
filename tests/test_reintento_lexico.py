"""El rescate léxico es una segunda oportunidad, no una segunda búsqueda fija.

Invariante: `fichas_lexicas` solo se consulta cuando el modelo ya contestó
"no encontré". Así una propuesta equivocada nunca puede desplazar a las fichas
que el vectorial había acertado.
"""

from types import SimpleNamespace

import pytest

from app.rag import prompts
from app.rag.fichas import Seccion
from app.rag.indice import Resultado
from app.rag.servicio import ServicioRAG


def seccion(ficha_id: str) -> Seccion:
    return Seccion(id=f"{ficha_id}::0", ficha_id=ficha_id, titulo=ficha_id.upper(),
                   nombre="Sección", url=f"https://udea.edu.co/{ficha_id}",
                   cuerpo=f"contenido de {ficha_id}")


class IndiceFalso:
    def __init__(self, densas: list[str], rescate: list[str],
                 en_disco: list[str] | None = None):
        # `en_disco`: fichas con secciones. Por defecto, las densas más las
        # rescatadas (la ficha correcta existe, solo que el vectorial no la trajo).
        self._densas = [seccion(f) for f in densas]
        self._fichas = [seccion(f) for f in (en_disco or densas + rescate)]
        self._rescate = rescate
        self.rescates_pedidos: list[list[str]] = []

    def buscar(self, pregunta: str, k: int) -> list[Resultado]:
        return [Resultado(texto=s.texto, ficha_id=s.ficha_id, titulo=s.titulo,
                          seccion=s.nombre, url=s.url, distancia=0.3, id=s.id,
                          tipo="seccion", seccion_id=s.id) for s in self._densas]

    def seccion(self, seccion_id: str):
        return next((s for s in self._fichas if s.id == seccion_id), None)

    def secciones_de_ficha(self, ficha_id: str) -> list[Seccion]:
        return [s for s in self._fichas if s.ficha_id == ficha_id]

    def fichas_lexicas(self, pregunta: str, ya_elegidas: list[str]) -> list[str]:
        self.rescates_pedidos.append(ya_elegidas)
        return self._rescate


class LLMFalso:
    def __init__(self, respuestas: list[str]):
        self._respuestas = list(respuestas)
        self.contextos: list[str] = []

    def generar(self, sistema: str, usuario: str):
        self.contextos.append(usuario)
        texto = self._respuestas.pop(0)
        return SimpleNamespace(texto=texto, recortada=False)


AJUSTES = SimpleNamespace(
    canal_oficial_url="https://udea.edu.co/comite",
    rag_top_k=8,
    rag_contexto_max_tokens=1500,
    rag_max_distance=0.5,
    llm_max_tokens=1200,
)

SIN_INFO = prompts.RESPUESTA_FUERA_DE_ALCANCE.format(canal_oficial=AJUSTES.canal_oficial_url)


def servicio(indice: IndiceFalso, llm: LLMFalso) -> ServicioRAG:
    return ServicioRAG(AJUSTES, indice, llm)


def test_si_el_modelo_responde_no_se_busca_lexicamente():
    indice = IndiceFalso(["a"], ["b"])
    r = servicio(indice, LLMFalso(["La respuesta es esta."])).responder("¿pregunta?")
    assert r.respuesta == "La respuesta es esta."
    assert indice.rescates_pedidos == []


def test_tras_un_no_encontre_reintenta_con_las_fichas_del_lexico():
    indice = IndiceFalso(["equivocada"], ["correcta"])
    llm = LLMFalso([SIN_INFO, "La respuesta ahora sí."])
    r = servicio(indice, llm).responder("¿pregunta?")
    assert r.respuesta == "La respuesta ahora sí."
    assert indice.rescates_pedidos == [["equivocada"]]
    assert len(llm.contextos) == 2
    # El segundo intento lleva la ficha rescatada; el primero no.
    assert "contenido de correcta" in llm.contextos[1]
    assert "contenido de correcta" not in llm.contextos[0]
    assert r.fichas_usadas[0] == "correcta"


def test_si_el_reintento_tampoco_sabe_queda_fuera_de_alcance():
    indice = IndiceFalso(["equivocada"], ["tampoco-sirve"])
    r = servicio(indice, LLMFalso([SIN_INFO, SIN_INFO])).responder("¿pregunta?")
    assert r.fuera_de_alcance is True
    assert r.respuesta == SIN_INFO


def test_sin_fragmentos_bajo_el_umbral_no_se_llama_al_modelo():
    class IndiceVacio(IndiceFalso):
        def buscar(self, pregunta, k):
            return [Resultado(texto="lejano", ficha_id="z", titulo="Z", seccion="",
                              url="", distancia=0.9, id="z::0", tipo="seccion",
                              seccion_id="z::0")]

    llm = LLMFalso([])
    r = servicio(IndiceVacio(["a"], ["b"]), llm).responder("¿pregunta?")
    assert r.fuera_de_alcance is True
    assert llm.contextos == []


@pytest.mark.parametrize("texto", ["No encontré información sobre eso.",
                                   "  no ENCONTRÉ INFORMACIÓN sobre eso, lo siento"])
def test_reconoce_la_negativa_aunque_cambie_el_espaciado(texto):
    from app.rag.servicio import es_sin_informacion

    assert es_sin_informacion(texto) is True
