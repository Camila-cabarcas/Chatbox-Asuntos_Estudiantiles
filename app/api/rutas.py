"""
Endpoints de la API REST (capa de lógica expuesta al frontend).

  GET  /api/health                         estado del sistema
  POST /api/chat                           pregunta -> respuesta con fuentes
  POST /api/consultas/{id}/valoracion      el estudiante marca si le fue útil
"""

import logging
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from app.api.schemas import EstadoOut, Fuente, PreguntaIn, RespuestaOut, ValoracionIn
from app.utils.privacidad import enmascarar

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@router.get("/health", response_model=EstadoOut)
def health(request: Request) -> EstadoOut:
    st = request.app.state
    return EstadoOut(
        estado="ok",
        base_datos=st.db.estado,
        fragmentos_indexados=st.indice.total(),
        proveedor_llm=st.llm.nombre,
        proveedor_embeddings=st.embeddings.nombre,
    )


@router.post("/chat", response_model=RespuestaOut)
async def chat(datos: PreguntaIn, request: Request) -> RespuestaOut:
    st = request.app.state
    # Se enmascara ANTES de enviarla al modelo externo y de guardarla.
    pregunta = enmascarar(datos.pregunta.strip())

    inicio = time.perf_counter()
    # El RAG hace trabajo bloqueante (embeddings, HTTP); se ejecuta en un
    # hilo aparte para no congelar el servidor.
    resultado = await run_in_threadpool(st.servicio.responder, pregunta)
    latencia_ms = int((time.perf_counter() - inicio) * 1000)

    id_consulta = await run_in_threadpool(
        st.repositorio.registrar,
        pregunta=pregunta,
        respuesta=resultado.respuesta,
        fichas_usadas=resultado.fichas_usadas,
        fuera_de_alcance=resultado.fuera_de_alcance,
        error=resultado.error,
        latencia_ms=latencia_ms,
        proveedor_llm=st.llm.nombre,
    )
    log.info("Consulta respondida en %d ms (fuera_de_alcance=%s)",
             latencia_ms, resultado.fuera_de_alcance)

    return RespuestaOut(
        respuesta=resultado.respuesta,
        fuentes=[Fuente(**f) for f in resultado.fuentes],
        fuera_de_alcance=resultado.fuera_de_alcance,
        id_consulta=id_consulta,
    )


@router.post("/consultas/{id_consulta}/valoracion", status_code=204)
def valorar(id_consulta: int, datos: ValoracionIn, request: Request) -> None:
    if not request.app.state.repositorio.valorar(id_consulta, datos.util):
        raise HTTPException(404, "Consulta no encontrada o base de datos no disponible")
