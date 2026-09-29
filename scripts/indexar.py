"""
Reconstruye el índice vectorial a partir de la carpeta fichas/.

Úsenlo después de crear o editar fichas, para probar sin reiniciar el
servidor, y para ver advertencias de fichas mal escritas:

    python -m scripts.indexar
    python -m scripts.indexar --probar "¿Cuándo se reúne el comité?"
"""

import argparse

from app.config import get_settings
from app.rag.embeddings import crear_embeddings
from app.rag.indice import IndiceVectorial
from app.utils.logs import configurar_logs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probar", help="Pregunta de prueba para ver qué fragmentos recupera.")
    args = ap.parse_args()

    s = get_settings()
    configurar_logs(s.log_level)
    indice = IndiceVectorial(s, crear_embeddings(s))
    total = indice.reconstruir()
    print(f"\nFragmentos indexados: {total}")

    if args.probar:
        print(f"\nPregunta: {args.probar}")
        print(f"(umbral de distancia: {s.rag_max_distance}; menor = más parecido)\n")
        for r in indice.buscar(args.probar, s.rag_top_k):
            marca = "✔" if r.distancia <= s.rag_max_distance else "✘ (descartado)"
            print(f"{marca} {r.distancia:.3f}  {r.titulo} › {r.seccion}")


if __name__ == "__main__":
    main()
