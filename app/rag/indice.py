"""
Índice vectorial con ChromaDB: guarda los fragmentos de las fichas con su
vector y permite buscar los más parecidos a una pregunta.
"""

import logging
from dataclasses import dataclass

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import Settings
from app.rag.embeddings import Embeddings
from app.rag.fichas import Fragmento, cargar_fragmentos

log = logging.getLogger(__name__)


@dataclass
class Resultado:
    texto: str
    ficha_id: str
    titulo: str
    seccion: str
    url: str
    distancia: float


class IndiceVectorial:
    def __init__(self, settings: Settings, embeddings: Embeddings):
        self._settings = settings
        self._embeddings = embeddings
        settings.chroma_path.mkdir(parents=True, exist_ok=True)
        self._cliente = chromadb.PersistentClient(
            path=str(settings.chroma_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._coleccion = self._obtener_coleccion()

    def _obtener_coleccion(self):
        return self._cliente.get_or_create_collection(
            name=self._settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )

    def total(self) -> int:
        return self._coleccion.count()

    def reconstruir(self) -> int:
        """Borra el índice y lo vuelve a crear desde la carpeta de fichas."""
        fragmentos: list[Fragmento] = cargar_fragmentos(self._settings.fichas_path)
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
            embeddings=self._embeddings.embed([f.texto for f in fragmentos]),
            metadatas=[{"ficha_id": f.ficha_id, "titulo": f.titulo,
                        "seccion": f.seccion, "url": f.url} for f in fragmentos],
        )
        log.info("Índice reconstruido con %d fragmentos.", len(fragmentos))
        return len(fragmentos)

    def buscar(self, pregunta: str, k: int) -> list[Resultado]:
        if self.total() == 0:
            return []
        r = self._coleccion.query(
            query_embeddings=self._embeddings.embed([pregunta]),
            n_results=min(k, self.total()),
        )
        return [
            Resultado(texto=doc, distancia=dist, **{
                "ficha_id": meta["ficha_id"], "titulo": meta["titulo"],
                "seccion": meta["seccion"], "url": meta["url"]})
            for doc, meta, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0])
        ]
