"""
Punto de entrada del backend.

Ejecutar en desarrollo:
    uvicorn app.main:app --reload

Arquitectura en tres capas (según el anteproyecto):
  - Presentación: carpeta frontend/ (servida por este mismo servidor en "/")
  - Lógica:       API REST en app/api + servicio RAG en app/rag
  - Conocimiento: fichas/ + índice ChromaDB (data/chroma) + PostgreSQL (app/db)
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.rutas import router
from app.config import RAIZ_PROYECTO, get_settings
from app.db.conexion import BaseDeDatos
from app.db.repositorio import RepositorioConsultas
from app.rag.embeddings import crear_embeddings
from app.rag.indice import IndiceVectorial
from app.rag.llm import crear_llm
from app.rag.servicio import ServicioRAG
from app.utils.logs import configurar_logs

log = logging.getLogger(__name__)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    s = get_settings()
    configurar_logs(s.log_level)
    log.info("Iniciando en modo %s | LLM=%s | embeddings=%s",
             s.app_env, s.llm_provider, s.embeddings_provider)

    st = app.state
    st.embeddings = crear_embeddings(s)
    st.indice = IndiceVectorial(s, st.embeddings)
    if s.index_on_startup:
        st.indice.reconstruir()
    elif not st.indice.vigente():
        log.warning("El índice está vacío o lo generó otro modelo de embeddings: se reconstruye.")
        st.indice.reconstruir()
    st.llm = crear_llm(s)
    st.servicio = ServicioRAG(s, st.indice, st.llm)
    st.db = BaseDeDatos(s)
    st.repositorio = RepositorioConsultas(st.db)

    yield

    st.db.cerrar()
    log.info("Servidor detenido.")


def crear_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=s.app_name,
        version="0.1.0",
        lifespan=ciclo_de_vida,
        # La documentación interactiva (/docs) solo fuera de producción.
        docs_url=None if s.app_env == "production" else "/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def revalidar_widget(request: Request, call_next):
        # El widget se inserta en otras páginas: el navegador debe preguntar
        # si hay una versión nueva (ETag) en vez de usar una copia vieja.
        # Si no cambió, el servidor responde 304 sin reenviar el archivo.
        respuesta = await call_next(request)
        if request.url.path.startswith("/widget/"):
            respuesta.headers["Cache-Control"] = "no-cache"
        return respuesta

    app.include_router(router)

    frontend = RAIZ_PROYECTO / "frontend"
    if (frontend / "index.html").exists():
        # Se monta al final para que no tape las rutas /api.
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = crear_app()
