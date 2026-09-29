import logging


def configurar_logs(nivel: str = "INFO") -> None:
    logging.basicConfig(
        level=nivel.upper(),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
    # Librerías muy habladoras: solo advertencias.
    for ruidoso in ("httpx", "chromadb", "sentence_transformers", "urllib3"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
