"""
Índice vectorial con ChromaDB: guarda los fragmentos de búsqueda de las
fichas con su vector y permite buscar los más parecidos a una pregunta.

Además conserva en memoria las secciones completas de cada ficha, que son
las que se entregan al modelo de lenguaje (ver app/rag/contexto.py).
"""

import logging
from dataclasses import dataclass
from typing import cast

import chromadb
from chromadb.api.types import PyEmbeddings
from chromadb.config import Settings as ChromaSettings

from app.config import Settings
from app.rag.embeddings import Embeddings
from app.rag.fichas import Ficha, Seccion, cargar_fichas, fragmentos_de, secciones_de

log = logging.getLogger(__name__)


@dataclass
class Resultado:
    texto: str
    ficha_id: str
    titulo: str
    seccion: str
    url: str
    distancia: float
    id: str = ""
    tipo: str = "seccion"
    seccion_id: str = ""


class IndiceVectorial:
    def __init__(self, settings: Settings, embeddings: Embeddings):
        self._settings = settings
        self._embeddings = embeddings
        # El fragmento no puede superar lo que el modelo de embeddings lee.
        self.limite_fragmento = min(settings.rag_fragmento_max_tokens, embeddings.max_tokens)
        settings.chroma_path.mkdir(parents=True, exist_ok=True)
        self._cliente = chromadb.PersistentClient(
            path=str(settings.chroma_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._coleccion = self._obtener_coleccion()
        self._secciones: dict[str, Seccion] = {}
        self._secciones_por_ficha: dict[str, list[Seccion]] = {}

    def _obtener_coleccion(self):
        return self._cliente.get_or_create_collection(
            name=self._settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )

    def _cargar_secciones(self, fichas: list[Ficha]) -> None:
        self._secciones_por_ficha = {f.id: secciones_de(f) for f in fichas}
        self._secciones = {s.id: s for ss in self._secciones_por_ficha.values() for s in ss}

    def _asegurar_secciones(self) -> None:
        # Si el índice no se reconstruyó al arrancar (INDEX_ON_STARTUP=false),
        # las secciones se leen de las fichas la primera vez que se necesitan.
        if not self._secciones_por_ficha:
            self._cargar_secciones(cargar_fichas(self._settings.fichas_path))

    def seccion(self, seccion_id: str) -> Seccion | None:
        self._asegurar_secciones()
        return self._secciones.get(seccion_id)

    def secciones_de_ficha(self, ficha_id: str) -> list[Seccion]:
        self._asegurar_secciones()
        return self._secciones_por_ficha.get(ficha_id, [])

    def total(self) -> int:
        return self._coleccion.count()

    def reconstruir(self) -> int:
        """Borra el índice y lo vuelve a crear desde la carpeta de fichas."""
        fichas = cargar_fichas(self._settings.fichas_path)
        self._cargar_secciones(fichas)
        fragmentos = fragmentos_de(
            fichas,
            contar=self._embeddings.contar_tokens,
            limite=self.limite_fragmento,
            solapamiento=self._settings.rag_fragmento_solapamiento,
            avisar=self._embeddings.conteo_exacto,
        )
        try:
            self._cliente.delete_collection(self._settings.chroma_collection)
        except Exception:  # la colección no existía
            pass
        self._coleccion = self._obtener_coleccion()
        if not fragmentos:
            log.warning("No hay fichas válidas para indexar.")
            return 0
        self._coleccion.add(
            ids=[f.id for f in fragmentos],
            documents=[f.texto for f in fragmentos],
            embeddings=cast(PyEmbeddings, self._embeddings.embed([f.texto for f in fragmentos])),
            metadatas=[{"ficha_id": f.ficha_id, "titulo": f.titulo, "seccion": f.seccion,
                        "url": f.url, "tipo": f.tipo, "seccion_id": f.seccion_id}
                       for f in fragmentos],
        )
        log.info("Índice reconstruido con %d fragmentos (máx. %d tokens cada uno).",
                 len(fragmentos), self.limite_fragmento)
        return len(fragmentos)

    def buscar(self, pregunta: str, k: int) -> list[Resultado]:
        if self.total() == 0:
            return []
        r = self._coleccion.query(
            query_embeddings=cast(PyEmbeddings, self._embeddings.embed([pregunta])),
            n_results=min(k, self.total()),
        )
        # Chroma declara estos campos como opcionales; con la consulta por
        # defecto siempre vienen, pero se usa [] como respaldo.
        ids = r["ids"][0] if r["ids"] else []
        documentos = (r["documents"] or [[]])[0]
        metadatos = (r["metadatas"] or [[]])[0]
        distancias = (r["distances"] or [[]])[0]
        return [
            Resultado(
                texto=doc, distancia=dist, id=id_,
                ficha_id=str(meta["ficha_id"]), titulo=str(meta["titulo"]),
                seccion=str(meta["seccion"]), url=str(meta["url"]),
                # Índices creados antes del troceado no tienen estos campos.
                tipo=str(meta.get("tipo") or "seccion"),
                seccion_id=str(meta.get("seccion_id") or ""),
            )
            for id_, doc, meta, dist in zip(ids, documentos, metadatos, distancias)
        ]
