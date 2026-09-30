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

from fastapi import FastAPI
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
    if s.index_on_startup or st.indice.total() == 0:
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
    app.include_router(router)

    frontend = RAIZ_PROYECTO / "frontend"
    if (frontend / "index.html").exists():
        # Se monta al final para que no tape las rutas /api.
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = crear_app()
