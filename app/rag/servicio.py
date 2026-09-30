"""
Servicio RAG: la función central del chatbot.

    pregunta -> buscar fragmentos -> construir instrucción -> modelo -> respuesta

Es la "función responder" acordada en el equipo. La API la usa sin saber
cómo funciona por dentro, así que el rol de IA puede cambiarla libremente
mientras respete la clase ResultadoRAG.
"""

import logging
from dataclasses import dataclass, field

from app.config import Settings
from app.rag import prompts
from app.rag.indice import IndiceVectorial, Resultado
from app.rag.llm import LLM, LLMError

log = logging.getLogger(__name__)


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
            return ResultadoRAG(
                respuesta=prompts.RESPUESTA_FUERA_DE_ALCANCE.format(canal_oficial=canal),
                fuentes=[{"titulo": "Comité de Asuntos Estudiantiles - Facultad de Ingeniería",
                          "url": canal}],
                fuera_de_alcance=True,
            )

        contexto = "\n\n---\n\n".join(r.texto for r in resultados)
        try:
            texto = self._llm.generar(
                sistema=prompts.PROMPT_SISTEMA.format(canal_oficial=canal),
                usuario=prompts.PLANTILLA_USUARIO.format(contexto=contexto, pregunta=pregunta),
            )
        except LLMError:
            return ResultadoRAG(
                respuesta=prompts.RESPUESTA_ERROR_LLM.format(canal_oficial=canal),
                fuentes=[{"titulo": "Canal oficial", "url": canal}],
                error=True,
            )

        return ResultadoRAG(
            respuesta=texto,
            fuentes=_fuentes_unicas(resultados),
            fichas_usadas=list(dict.fromkeys(r.ficha_id for r in resultados)),
        )


def _fuentes_unicas(resultados: list[Resultado]) -> list[dict]:
    vistas, salida = set(), []
    for r in resultados:
        if r.url and r.url not in vistas:
            vistas.add(r.url)
            salida.append({"titulo": r.titulo, "url": r.url})
    return salida
