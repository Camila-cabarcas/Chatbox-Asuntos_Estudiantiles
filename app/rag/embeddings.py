"""
Embeddings: convierten texto en vectores para buscar por significado.

Proveedores (se elige con EMBEDDINGS_PROVIDER en .env):
  - onnx:  el mismo modelo multilingüe, exportado a ONNX y cuantizado a
           int8, con ONNX Runtime y SentencePiece. No necesita PyTorch y
           usa mucha menos memoria: es el modo de despliegue (Render). Los
           archivos se descargan con `python -m scripts.descargar_modelo`.
  - local: modelo multilingüe preentrenado con sentence-transformers
           (PyTorch), como indica el anteproyecto. Para desarrollo y para
           comparar con el ONNX. La primera vez descarga el modelo.
  - mock:  vectores simples basados en palabras. No descarga nada; sirve
           para pruebas automáticas y para trabajar sin internet.

Para agregar otro proveedor (p. ej. embeddings por API) basta con crear
una clase con `embed`, `contar_tokens` y `max_tokens` y registrarla en
`crear_embeddings`.

`max_tokens` es lo máximo que el modelo lee de cada texto: lo que pase de
ahí se descarta en silencio. Las fichas se trocean para no superarlo.
"""

import hashlib
import logging
import math
import re
import unicodedata
from pathlib import Path
from typing import Protocol

from app.config import Settings
from app.rag.tokens import estimar_tokens

log = logging.getLogger(__name__)


class Embeddings(Protocol):
    nombre: str
    max_tokens: int
    # True si contar_tokens usa el tokenizador del modelo (y no una estimación).
    conteo_exacto: bool

    def embed(self, textos: list[str]) -> list[list[float]]: ...

    def contar_tokens(self, texto: str) -> int: ...


class EmbeddingsLocal:
    def __init__(self, modelo: str):
        try:
            from sentence_transformers import SentenceTransformer  # pyright: ignore[reportMissingImports]
        except ImportError as e:
            raise RuntimeError(
                "EMBEDDINGS_PROVIDER=local requiere 'sentence-transformers'. "
                "Instálelo con: pip install -r requirements-embeddings.txt "
                "o use EMBEDDINGS_PROVIDER=mock mientras tanto."
            ) from e
        log.info("Cargando modelo de embeddings '%s' (la primera vez tarda)...", modelo)
        self._modelo = SentenceTransformer(modelo)
        self.nombre = f"local:{modelo}"
        self.max_tokens = int(self._modelo.max_seq_length or 512)
        self.conteo_exacto = True

    def embed(self, textos: list[str]) -> list[list[float]]:
        vectores = self._modelo.encode(textos, normalize_embeddings=True)
        return [v.tolist() for v in vectores]

    def contar_tokens(self, texto: str) -> int:
        # verbose=False: no avisar cuando el texto medido supera el límite
        # (justamente se mide para decidir si hay que dividirlo).
        return len(self._modelo.tokenizer(texto, verbose=False)["input_ids"])


class EmbeddingsOnnx:
    """MiniLM-L12 en ONNX int8: tokeniza con SentencePiece, corre el modelo
    con ONNX Runtime y promedia los vectores de los tokens (mean pooling),
    igual que sentence-transformers con este modelo.

    Pensado para un servidor pequeño: un solo hilo y sin el arena de memoria
    de ONNX Runtime (que retiene la memoria del lote más grande que haya
    visto).

    Cada texto se procesa solo (LOTE = 1). El modelo int8 cuantiza las
    activaciones con una escala calculada sobre todo el lote, así que en un
    lote de varios textos el vector de cada uno depende de sus vecinos (y
    del relleno): el mismo fragmento cambiaba según con qué textos se
    indexara, y no coincidía con la pregunta, que se procesa sola. Con un
    texto por lote los vectores son reproducibles y no hay relleno."""

    LOTE = 1
    # El tokenizador de XLM-R (el de este modelo) usa los ids de fairseq:
    # cuatro especiales al inicio y el resto del vocabulario de SentencePiece
    # corrido en 1. El id 0 de SentencePiece es su <unk>.
    BOS, PAD, EOS, UNK = 0, 1, 2, 3
    _DESPLAZAMIENTO = 1

    def __init__(self, ruta_modelo: Path, ruta_tokenizador: Path, nombre: str,
                 max_tokens: int = 128):
        try:
            import numpy as np
            import onnxruntime as ort
            import sentencepiece as spm
        except ImportError as e:
            raise RuntimeError(
                "EMBEDDINGS_PROVIDER=onnx requiere 'onnxruntime', 'sentencepiece' y 'numpy'. "
                "Instálelos con: pip install -r requirements.txt"
            ) from e
        faltan = [str(r) for r in (ruta_modelo, ruta_tokenizador) if not r.is_file()]
        if faltan:
            raise RuntimeError(
                "Faltan los archivos del modelo ONNX: " + ", ".join(faltan)
                + ". Descárguelos con: python -m scripts.descargar_modelo"
            )
        log.info("Cargando modelo de embeddings ONNX '%s'...", ruta_modelo.name)
        opciones = ort.SessionOptions()
        opciones.intra_op_num_threads = 1
        opciones.inter_op_num_threads = 1
        opciones.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        opciones.enable_cpu_mem_arena = False
        opciones.log_severity_level = 3   # solo errores
        self._np = np
        self._sesion = ort.InferenceSession(str(ruta_modelo), opciones,
                                            providers=["CPUExecutionProvider"])
        self._entradas = {e.name for e in self._sesion.get_inputs()}
        self._sp = spm.SentencePieceProcessor(model_file=str(ruta_tokenizador))
        self.nombre = f"onnx:{nombre}/{ruta_modelo.name}"
        # 128 es el max_seq_length de MiniLM-L12 (sentence_bert_config.json).
        self.max_tokens = max_tokens
        self.conteo_exacto = True

    def _ids(self, texto: str) -> list[int]:
        """Ids del texto con <s> y </s>, sin recortar."""
        piezas = self._sp.encode(texto)
        return ([self.BOS]
                + [i + self._DESPLAZAMIENTO if i else self.UNK for i in piezas]
                + [self.EOS])

    def contar_tokens(self, texto: str) -> int:
        return len(self._ids(texto))

    def _recortar(self, ids: list[int]) -> list[int]:
        # Como sentence-transformers: se conservan los primeros tokens y el </s>.
        if len(ids) <= self.max_tokens:
            return ids
        return ids[: self.max_tokens - 1] + [self.EOS]

    def embed(self, textos: list[str]) -> list[list[float]]:
        np = self._np
        salida: list[list[float]] = []
        for i in range(0, len(textos), self.LOTE):
            lote = [self._recortar(self._ids(t)) for t in textos[i:i + self.LOTE]]
            largo = max(len(ids) for ids in lote)
            input_ids = np.full((len(lote), largo), self.PAD, dtype=np.int64)
            mascara = np.zeros((len(lote), largo), dtype=np.int64)
            for fila, ids in enumerate(lote):
                input_ids[fila, :len(ids)] = ids
                mascara[fila, :len(ids)] = 1
            entradas = {"input_ids": input_ids, "attention_mask": mascara}
            if "token_type_ids" in self._entradas:
                entradas["token_type_ids"] = np.zeros_like(input_ids)
            tokens = self._sesion.run(None, entradas)[0]          # (lote, largo, 384)
            peso = mascara[:, :, None].astype(np.float32)
            medias = (tokens * peso).sum(axis=1) / np.clip(peso.sum(axis=1), 1e-9, None)
            normas = np.clip(np.linalg.norm(medias, axis=1, keepdims=True), 1e-12, None)
            salida.extend((medias / normas).tolist())
        return salida


class EmbeddingsMock:
    """Bolsa de palabras con hashing. NO entiende sinónimos; solo sirve
    para desarrollo y pruebas."""

    DIM = 384

    def __init__(self):
        self.nombre = "mock"
        # Sin tokenizador: no hay un límite propio; manda RAG_FRAGMENTO_MAX_TOKENS.
        self.max_tokens = 512
        self.conteo_exacto = False

    def contar_tokens(self, texto: str) -> int:
        return estimar_tokens(texto)

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
    if settings.embeddings_provider == "onnx":
        return EmbeddingsOnnx(settings.embeddings_onnx_ruta, settings.embeddings_tokenizador_ruta,
                              settings.embeddings_model)
    if settings.embeddings_provider == "local":
        return EmbeddingsLocal(settings.embeddings_model)
    return EmbeddingsMock()
