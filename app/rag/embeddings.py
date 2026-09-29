"""
Embeddings: convierten texto en vectores para buscar por significado.

Proveedores (se elige con EMBEDDINGS_PROVIDER en .env):
  - local: modelo multilingüe preentrenado con sentence-transformers,
           como indica el anteproyecto. La primera vez descarga el modelo.
  - mock:  vectores simples basados en palabras. No descarga nada; sirve
           para pruebas automáticas y para trabajar sin internet.

Para agregar otro proveedor (p. ej. embeddings por API) basta con crear
una clase con el método `embed` y registrarla en `crear_embeddings`.
"""

import hashlib
import logging
import math
import re
import unicodedata
from typing import Protocol

from app.config import Settings

log = logging.getLogger(__name__)


class Embeddings(Protocol):
    nombre: str

    def embed(self, textos: list[str]) -> list[list[float]]: ...


class EmbeddingsLocal:
    def __init__(self, modelo: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError(
                "EMBEDDINGS_PROVIDER=local requiere 'sentence-transformers'. "
                "Instálelo con: pip install -r requirements-embeddings.txt "
                "o use EMBEDDINGS_PROVIDER=mock mientras tanto."
            ) from e
        log.info("Cargando modelo de embeddings '%s' (la primera vez tarda)...", modelo)
        self._modelo = SentenceTransformer(modelo)
        self.nombre = f"local:{modelo}"

    def embed(self, textos: list[str]) -> list[list[float]]:
        vectores = self._modelo.encode(textos, normalize_embeddings=True)
        return [v.tolist() for v in vectores]


class EmbeddingsMock:
    """Bolsa de palabras con hashing. NO entiende sinónimos; solo sirve
    para desarrollo y pruebas."""

    DIM = 384

    def __init__(self):
        self.nombre = "mock"

    @staticmethod
    def _palabras(texto: str) -> list[str]:
        texto = unicodedata.normalize("NFKD", texto.lower())
        texto = "".join(c for c in texto if not unicodedata.combining(c))
        return [p for p in re.findall(r"[a-z0-9]+", texto) if len(p) > 2]

    def embed(self, textos: list[str]) -> list[list[float]]:
        salida = []
        for texto in textos:
            v = [0.0] * self.DIM
            for palabra in self._palabras(texto):
                h = int(hashlib.md5(palabra.encode()).hexdigest(), 16)
                v[h % self.DIM] += 1.0
            norma = math.sqrt(sum(x * x for x in v)) or 1.0
            salida.append([x / norma for x in v])
        return salida


def crear_embeddings(settings: Settings) -> Embeddings:
    if settings.embeddings_provider == "local":
        return EmbeddingsLocal(settings.embeddings_model)
    return EmbeddingsMock()
