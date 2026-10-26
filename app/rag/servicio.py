"""
Servicio RAG: la función central del chatbot.

    pregunta -> buscar fragmentos -> armar contexto con las secciones
             completas -> construir instrucción -> modelo -> respuesta

Es la "función responder" acordada en el equipo. La API la usa sin saber
cómo funciona por dentro, así que el rol de IA puede cambiarla libremente
mientras respete la clase ResultadoRAG.
"""

import logging
from dataclasses import dataclass, field

from app.config import Settings
from app.rag import prompts
from app.rag.contexto import armar_contexto
from app.rag.indice import IndiceVectorial, Resultado
from app.rag.llm import LLM, LLMError, quitar_razonamiento

log = logging.getLogger(__name__)


def es_sin_informacion(texto: str) -> bool:
    """El modelo empezó con la frase acordada para "no hay información"."""
    inicio = texto.lstrip(" \t\n\"'«*_").casefold()
    return inicio.startswith(prompts.FRASE_SIN_INFORMACION.casefold())


@dataclass
class ResultadoRAG:
    respuesta: str
    fuentes: list[dict] = field(default_factory=list)   # [{"titulo", "url"}]
    fichas_usadas: list[str] = field(default_factory=list)
    fuera_de_alcance: bool = False
    error: bool = False


class ServicioRAG:
    def __init__(self, settings: Settings, indice: IndiceVectorial, llm: LLM):
        self._s = settings
        self._indice = indice
        self._llm = llm

    def responder(self, pregunta: str) -> ResultadoRAG:
        canal = self._s.canal_oficial_url
        resultados = [r for r in self._indice.buscar(pregunta, self._s.rag_top_k)
                      if r.distancia <= self._s.rag_max_distance]

        if not resultados:
            return self._fuera_de_alcance()

        contexto = "\n\n---\n\n".join(
            armar_contexto(resultados, self._indice, self._s.rag_contexto_max_tokens))
        try:
            r = self._llm.generar(
                sistema=prompts.sistema(canal),
                usuario=prompts.PLANTILLA_USUARIO.format(contexto=contexto, pregunta=pregunta),
            )
        except LLMError:
            return self._error()

        texto = quitar_razonamiento(r.texto)
        if not texto:
            log.warning("El modelo no devolvió respuesta (solo razonamiento interno o texto vacío).")
            return self._error()
        if es_sin_informacion(texto):
            # El modelo concluyó que las fichas encontradas no responden la pregunta.
            return self._fuera_de_alcance()
        if r.recortada:
            log.warning("El modelo cortó la respuesta al llegar a LLM_MAX_TOKENS=%d.",
                        self._s.llm_max_tokens)
            texto += prompts.NOTA_RESPUESTA_INCOMPLETA.format(canal_oficial=canal)

        return ResultadoRAG(
            respuesta=texto,
            fuentes=_fuentes_unicas(resultados),
            fichas_usadas=list(dict.fromkeys(x.ficha_id for x in resultados)),
        )

    def _fuera_de_alcance(self) -> ResultadoRAG:
        canal = self._s.canal_oficial_url
        return ResultadoRAG(
            respuesta=prompts.RESPUESTA_FUERA_DE_ALCANCE.format(canal_oficial=canal),
            fuentes=[{"titulo": "Comité de Asuntos Estudiantiles - Facultad de Ingeniería",
                      "url": canal}],
            fuera_de_alcance=True,
        )

    def _error(self) -> ResultadoRAG:
        canal = self._s.canal_oficial_url
        return ResultadoRAG(
            respuesta=prompts.RESPUESTA_ERROR_LLM.format(canal_oficial=canal),
            fuentes=[{"titulo": "Canal oficial", "url": canal}],
            error=True,
        )


def _fuentes_unicas(resultados: list[Resultado]) -> list[dict]:
    vistas, salida = set(), []
    for r in resultados:
        if r.url and r.url not in vistas:
            vistas.add(r.url)
            salida.append({"titulo": r.titulo, "url": r.url})
    return salida
