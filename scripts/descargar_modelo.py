"""
Descarga el modelo de embeddings en ONNX int8 y construye el índice con él
(EMBEDDINGS_PROVIDER=onnx). Se usa una vez en desarrollo y en el build de
Docker, así el servidor arranca sin descargar nada:

    python -m scripts.descargar_modelo
    python -m scripts.descargar_modelo --sin-indice    # solo descarga

Baja dos archivos del repositorio de Hugging Face del modelo
(EMBEDDINGS_MODEL), fijado en una versión concreta para que el modelo no
cambie sin que nadie se entere:
  onnx/<EMBEDDINGS_ONNX_ARCHIVO>   el modelo cuantizado a int8 (~118 MB)
  sentencepiece.bpe.model          el tokenizador (~5 MB)
y los deja en EMBEDDINGS_ONNX_DIR (models/ por defecto, ignorada por Git).
Si ya están, no se vuelven a descargar.

El índice se construye en CHROMA_PATH con la configuración del .env (o de
las variables de entorno), pero siempre con EMBEDDINGS_PROVIDER=onnx.
"""

import argparse
import logging

from app.config import get_settings
from app.rag.embeddings import crear_embeddings
from app.rag.indice import IndiceVectorial
from app.utils.logs import configurar_logs

log = logging.getLogger(__name__)

# Versión (commit) del repositorio de Hugging Face del modelo por defecto.
# Si se cambia, hay que volver a calibrar RAG_MAX_DISTANCE.
REVISIONES = {
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2":
        "e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
}
TOKENIZADOR = "sentencepiece.bpe.model"


def descargar(modelo: str, archivo_onnx: str, destino, revision: str | None = None) -> None:
    from huggingface_hub import hf_hub_download

    revision = revision or REVISIONES.get(modelo, "main")
    for nombre in (f"onnx/{archivo_onnx}", TOKENIZADOR):
        ruta = hf_hub_download(modelo, nombre, revision=revision, local_dir=destino)
        log.info("Listo: %s", ruta)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sin-indice", action="store_true", help="Solo descarga; no construye el índice.")
    ap.add_argument("--revision", help="Commit del repositorio del modelo (por defecto, el fijado aquí).")
    args = ap.parse_args()

    s = get_settings().model_copy(update={"embeddings_provider": "onnx"})
    configurar_logs(s.log_level)
    descargar(s.embeddings_model, s.embeddings_onnx_archivo, s.embeddings_onnx_dir, args.revision)
    if args.sin_indice:
        return
    embeddings = crear_embeddings(s)
    total = IndiceVectorial(s, embeddings).reconstruir()
    print(f"\nFragmentos indexados con {embeddings.nombre}: {total} en {s.chroma_path}")


if __name__ == "__main__":
    main()
