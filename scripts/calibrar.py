"""
Calibra la búsqueda con un banco de preguntas: qué ficha queda primero, si
la esperada está entre las primeras fichas y a qué distancia, para elegir
modelo de embeddings y RAG_MAX_DISTANCE.

    python -m scripts.calibrar --proveedor mock
    python -m scripts.calibrar --proveedor local --modelo sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

El índice se construye en una carpeta temporal (no toca data/) y NO se lee
el archivo .env: el proveedor y el modelo se pasan por argumentos; el resto
de parámetros usa los valores por defecto de app/config.py.

CSV (tests/calibracion/preguntas.csv): pregunta, ficha_esperada,
dentro_alcance (true/false) y, opcional, tipo (dentro/universidad/sin_relacion).
"""

import argparse
import csv
import gc
import json
import logging
import statistics
import sys
import tempfile
import time
from pathlib import Path

from chromadb.api.shared_system_client import SharedSystemClient

from app.config import RAIZ_PROYECTO, Settings
from app.rag.embeddings import crear_embeddings
from app.rag.indice import IndiceVectorial

CSV_POR_DEFECTO = RAIZ_PROYECTO / "tests" / "calibracion" / "preguntas.csv"


def memoria_maxima_mb() -> float | None:
    """Pico de memoria del proceso (MB), sin dependencias extra."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class Contadores(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

            kernel32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
            # Tipos explícitos: sin ellos, en 64 bits el identificador del
            # proceso se recorta y la llamada falla en silencio.
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Contadores),
                                                   wintypes.DWORD]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            c = Contadores()
            c.cb = ctypes.sizeof(c)
            if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb):
                return None
            return c.PeakWorkingSetSize / 2**20
        import resource
        pico = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return pico / 2**20 if sys.platform == "darwin" else pico / 2**10
    except Exception:
        return None


def leer_csv(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    for r in filas:
        r["dentro"] = r["dentro_alcance"].strip().lower() == "true"
        r["tipo"] = (r.get("tipo") or ("dentro" if r["dentro"] else "fuera")).strip()
    return filas


def fichas_en_orden(resultados) -> list[tuple[str, float]]:
    """Fichas distintas en el orden en que aparecen, con su mejor distancia."""
    vistas: dict[str, float] = {}
    for r in resultados:
        vistas.setdefault(r.ficha_id, r.distancia)
    return list(vistas.items())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proveedor", choices=["local", "mock"], required=True)
    ap.add_argument("--modelo", default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    ap.add_argument("--csv", type=Path, default=CSV_POR_DEFECTO)
    ap.add_argument("--top", type=int, default=4, help="Primeras N fichas distintas que cuentan como acierto.")
    ap.add_argument("--json", type=Path, help="Guarda el resultado detallado en este archivo.")
    args = ap.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    filas = leer_csv(args.csv)

    # ignore_cleanup_errors: respaldo por si Chroma aún tiene abierto su
    # archivo SQLite (Windows no deja borrar archivos abiertos).
    with tempfile.TemporaryDirectory(prefix="calibracion_", ignore_cleanup_errors=True) as tmp:
        # _env_file=None: no se lee .env.
        s = Settings(_env_file=None, embeddings_provider=args.proveedor,  # pyright: ignore[reportCallIssue]
                     embeddings_model=args.modelo, chroma_path=Path(tmp) / "chroma")
        t0 = time.perf_counter()
        embeddings = crear_embeddings(s)
        t_modelo = time.perf_counter() - t0

        t0 = time.perf_counter()
        indice = IndiceVectorial(s, embeddings)
        n_fragmentos = indice.reconstruir()
        t_indice = time.perf_counter() - t0

        detalle, tiempos = [], []
        for r in filas:
            t0 = time.perf_counter()
            # Se piden bastantes fragmentos para ver varias fichas distintas.
            resultados = indice.buscar(r["pregunta"], 40)
            tiempos.append(time.perf_counter() - t0)
            fichas = fichas_en_orden(resultados)
            primera, mejor = fichas[0] if fichas else ("", float("nan"))
            orden = [f for f, _ in fichas]
            esperada = r["ficha_esperada"]
            puesto = orden.index(esperada) + 1 if esperada in orden else None
            detalle.append({
                "pregunta": r["pregunta"], "tipo": r["tipo"], "dentro": r["dentro"],
                "esperada": esperada, "primera": primera, "mejor_distancia": round(mejor, 4),
                "acierto_1": r["dentro"] and primera == esperada,
                "acierto_top": r["dentro"] and puesto is not None and puesto <= args.top,
                "puesto": puesto,
            })
        memoria = memoria_maxima_mb()
        limite_fragmento = indice.limite_fragmento
        # Libera Chroma para que la carpeta temporal se pueda borrar.
        del indice
        SharedSystemClient.clear_system_cache()
        gc.collect()

    nombre = embeddings.nombre
    print(f"\n=== {nombre} | fragmentos: {n_fragmentos} (máx. {limite_fragmento} tokens)")
    print(f"{'tipo':12} {'dist':>6} {'1.º':>3} {'top' + str(args.top):>5} {'puesto':>6}  primera ficha  |  pregunta")
    for d in detalle:
        marca1 = ("✔" if d["acierto_1"] else "✘") if d["dentro"] else "-"
        marcat = ("✔" if d["acierto_top"] else "✘") if d["dentro"] else "-"
        print(f"{d['tipo']:12} {d['mejor_distancia']:6.3f} {marca1:>3} {marcat:>5} {str(d['puesto'] or '-'):>6}  "
              f"{d['primera'][:38]:38} | {d['pregunta'][:70]}")

    dentro = [d for d in detalle if d["dentro"]]
    fuera = [d for d in detalle if not d["dentro"]]
    dd = [d["mejor_distancia"] for d in dentro]
    df = [d["mejor_distancia"] for d in fuera]
    print(f"\nAciertos en 1.er lugar: {sum(d['acierto_1'] for d in dentro)}/{len(dentro)} | "
          f"entre las primeras {args.top} fichas: {sum(d['acierto_top'] for d in dentro)}/{len(dentro)}")
    print(f"Distancia del mejor fragmento  dentro: min {min(dd):.3f} · mediana {statistics.median(dd):.3f} · máx {max(dd):.3f}")
    print(f"                               fuera:  min {min(df):.3f} · mediana {statistics.median(df):.3f} · máx {max(df):.3f}")

    # Barrido del umbral: dentro si la mejor distancia <= umbral.
    candidatos = sorted(set(dd + df))
    barrido = []
    for u in candidatos:
        bien_dentro = sum(x <= u for x in dd)
        bien_fuera = sum(x > u for x in df)
        barrido.append((bien_dentro + bien_fuera, bien_dentro, bien_fuera, u))
    mejor_total = max(b[0] for b in barrido)
    empates = [i for i, b in enumerate(barrido) if b[0] == mejor_total]
    # Cualquier umbral desde la primera distancia empatada hasta justo antes
    # de la distancia siguiente a la última da el mismo resultado.
    lo = barrido[empates[0]][3]
    hi = barrido[empates[-1] + 1][3] if empates[-1] + 1 < len(barrido) else float("inf")
    print(f"Mejor separación: {mejor_total}/{len(detalle)} bien clasificadas con un umbral "
          f"≥ {lo:.3f} y < {hi:.3f}")
    print(f"Tiempos: carga del modelo {t_modelo:.1f} s · índice {t_indice:.1f} s · "
          f"consulta media {1000 * statistics.mean(tiempos):.0f} ms")
    print(f"Memoria máxima del proceso: {memoria:.0f} MB" if memoria else "Memoria: no disponible")

    if args.json:
        args.json.write_text(json.dumps({
            "modelo": nombre, "fragmentos": n_fragmentos, "detalle": detalle,
            "tiempo_modelo_s": t_modelo, "tiempo_indice_s": t_indice,
            "consulta_media_ms": 1000 * statistics.mean(tiempos), "memoria_mb": memoria,
        }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
