"""
Servicio RAG: la función central del chatbot.

    pregunta -> buscar fragmentos -> armar contexto con las secciones
             completas -> construir instrucción -> modelo -> respuesta

Es la "función responder" acordada en el equipo. La API la usa sin saber
cómo funciona por dentro, así que el rol de IA puede cambiarla libremente
mientras respete la clase ResultadoRAG.
"""

import logging
import re
import time
from dataclasses import dataclass, field

from app.config import Settings
from app.rag import prompts
from app.rag.contexto import armar_contexto
from app.rag.indice import IndiceVectorial, Resultado
from app.rag.llm import LLM, LLMError, quitar_razonamiento

log = logging.getLogger(__name__)

# Segundos de espera antes de reintentar una llamada fallida al modelo.
ESPERA_REINTENTO = 2.0
# Si el proveedor responde 429/503 sin decir cuánto esperar (límite por minuto
# o saturación), un reintento a los 2 s vuelve a fallar: se espera más.
ESPERA_LIMITE = 30.0
ESPERA_MAXIMA = 120.0


def _espera_reintento(error: LLMError) -> float:
    if error.retry_after is not None:
        espera = error.retry_after
    elif error.status in (429, 503):
        espera = ESPERA_LIMITE
    else:
        espera = ESPERA_REINTENTO
    return min(max(espera, ESPERA_REINTENTO), ESPERA_MAXIMA)


def es_sin_informacion(texto: str) -> bool:
    """El modelo empezó con la frase acordada para "no hay información"."""
    inicio = texto.lstrip(" \t\n\"'«*_").casefold()
    return inicio.startswith(prompts.FRASE_SIN_INFORMACION.casefold())


def quitar_cierre_sin_informacion(texto: str, canal: str) -> str:
    """Si el modelo ya respondió y al final pegó la frase de "sin información"
    (p. ej. porque faltaba un dato puntual), la reemplaza por una remisión
    corta, para que la respuesta no se contradiga."""
    i = texto.casefold().find(prompts.FRASE_SIN_INFORMACION.casefold())
    if i > 20:
        return (texto[:i].rstrip()
                + f"\n\nPara el dato que falta, consulta el canal oficial: {canal}")
    return texto


def limpiar_markdown(texto: str) -> str:
    """Regla 9 del prompt: texto plano. Quita asteriscos y comillas invertidas."""
    return re.sub(r"[*`]", "", texto)


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
        brutos = self._indice.buscar(pregunta, self._s.rag_top_k)
        # Diagnóstico: distancias de TODOS los fragmentos recuperados, para
        # calibrar RAG_MAX_DISTANCE con datos y no a ojo.
        log.info("Búsqueda: %r -> %s", pregunta[:80],
                 [(r.ficha_id, r.tipo, round(r.distancia, 4)) for r in brutos])
        resultados = [r for r in brutos if r.distancia <= self._s.rag_max_distance]

        if not resultados:
            return self._fuera_de_alcance()

        densas = list(dict.fromkeys(
            r.ficha_id for r in sorted(resultados, key=lambda x: x.distancia)))
        contexto = self._contexto(resultados, pregunta)

        r, texto = self._llamar(canal, contexto, pregunta)
        if r is None:
            return self._error()

        usadas = list(dict.fromkeys(x.ficha_id for x in resultados))
        if es_sin_informacion(texto):
            # El modelo concluyó que las fichas encontradas no responden. Antes
            # de rendirse se intenta una segunda búsqueda: el ranking léxico
            # propone fichas que el vectorial no trajo (ver app/rag/lexico.py).
            # Solo se llega aquí cuando la primera respuesta fue "no encontré",
            # así que una propuesta equivocada no puede dañar una respuesta que
            # ya era buena.
            prioritarias = self._indice.fichas_lexicas(pregunta, densas)
            contexto2 = (self._contexto(resultados, pregunta, prioritarias)
                         if prioritarias else contexto)
            if prioritarias and contexto2 != contexto:
                log.info("Sin respuesta con el vectorial; segundo intento con %s",
                         prioritarias)
                r2, texto2 = self._llamar(canal, contexto2, pregunta)
                if r2 is not None and not es_sin_informacion(texto2):
                    r, texto = r2, texto2
                    usadas = list(dict.fromkeys(prioritarias + usadas))
            if es_sin_informacion(texto):
                return self._fuera_de_alcance()
        texto = limpiar_markdown(quitar_cierre_sin_informacion(texto, canal))
        if r.recortada:
            log.warning("El modelo cortó la respuesta al llegar a LLM_MAX_TOKENS=%d.",
                        self._s.llm_max_tokens)
            texto += prompts.NOTA_RESPUESTA_INCOMPLETA.format(canal_oficial=canal)

        return ResultadoRAG(
            respuesta=texto,
            fuentes=self._fuentes(resultados, usadas),
            fichas_usadas=usadas,
        )

    def _fuentes(self, resultados: list[Resultado], fichas: list[str]) -> list[dict]:
        """Fuentes de los fragmentos recuperados y de las fichas rescatadas.

        Las fichas que propone el ranking léxico entran al contexto sin haber
        pasado por `buscar`, así que no están en `resultados`: se añaden aquí
        para que la respuesta no cite solo las fichas equivocadas.
        """
        fuentes = _fuentes_unicas(resultados)
        vistas = {f["url"] for f in fuentes}
        for ficha_id in fichas:
            secciones = self._indice.secciones_de_ficha(ficha_id)
            if not secciones:
                continue
            s = secciones[0]
            if s.url and s.url not in vistas:
                vistas.add(s.url)
                fuentes.append({"titulo": s.titulo, "url": s.url})
        return fuentes

    def _contexto(self, resultados: list[Resultado], pregunta: str,
                  prioritarias: list[str] | None = None) -> str:
        return "\n\n---\n\n".join(
            armar_contexto(resultados, self._indice, self._s.rag_contexto_max_tokens,
                           pregunta=pregunta, prioritarias=prioritarias))

    def _llamar(self, canal: str, contexto: str, pregunta: str):
        """Una llamada al modelo con reintento si el proveedor falla o llega
        vacío. Devuelve (None, "") solo cuando no hubo respuesta ninguna."""
        sistema = prompts.sistema(canal)
        usuario = prompts.PLANTILLA_USUARIO.format(contexto=contexto, pregunta=pregunta)
        r, texto = None, ""
        for intento in (1, 2):
            try:
                r = self._llm.generar(sistema=sistema, usuario=usuario)
                texto = quitar_razonamiento(r.texto)
            except LLMError as e:
                log.warning("Fallo del modelo (intento %d/2): %s", intento, e)
                r, texto = None, ""
                if intento == 1:
                    espera = _espera_reintento(e)
                    log.info("Reintentando en %.0f s.", espera)
                    time.sleep(espera)
                continue
            if texto:
                break
            if intento == 1:
                time.sleep(ESPERA_REINTENTO)
        if r is None or not texto:
            log.warning("El modelo no devolvió respuesta tras 2 intentos.")
            return None, ""
        return r, texto

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
