"""
Mide, sin llamar al modelo de lenguaje, si los datos esenciales de la
rúbrica llegan al contexto para las 30 preguntas del banco
(tests/evaluacion/banco_30.csv), y en qué puesto queda la ficha esperada.

    python -m scripts.medir_esenciales --proveedor onnx
    python -m scripts.medir_esenciales --proveedor onnx --presupuesto 1500 1800 2000
    python -m scripts.medir_esenciales --proveedor onnx --presupuesto 1800 --max-fichas 4 5 --proactivo 0 2

Cada combinación de --presupuesto (RAG_CONTEXTO_MAX_TOKENS), --max-fichas
(fichas candidatas en el contexto) y --proactivo se mide por separado; la
primera es la referencia con la que se comparan las demás.

--proactivo F (experimental): si una ficha que propone el ranking léxico, y
que el vectorial no trajo, puntúa al menos F veces lo que puntúa la mejor
ficha vectorial en el mismo ranking, entra ya en la primera llamada (como
si el rescate léxico se adelantara). 0 = apagado, como hoy.

Para cada pregunta se arman, igual que app/rag/servicio.py:
  1.ª llamada  el contexto con las fichas de la búsqueda vectorial;
  rescate      el que se usaría si el modelo responde "no encontré".
Una pregunta cuenta como recuperada si todos sus datos esenciales están en
la 1.ª llamada o, si faltan ahí, en el rescate (que solo ocurre si el modelo
dice "no encontré": es una cota optimista). El puesto de la ficha esperada
se informa porque que el dato llegue no basta: si la ficha correcta no es
la principal, el modelo puede responder "no encontré" igual.

Los datos esenciales se buscan con las expresiones de ESENCIALES (texto sin
tildes ni mayúsculas), escritas con las palabras de las fichas. Si se edita
el banco o una ficha cambia la redacción de un dato, hay que actualizarlas.
F01-F04 se cuentan bien si quedan fuera de alcance; R01-R03 califican la
conducta (no prometer un resultado) y no datos del contexto.

El índice se construye en una carpeta temporal y no se lee .env.
--json solo escribe archivos .json dentro de data/ (ignorada por Git).
"""

import argparse
import csv
import itertools
import logging
import re
import statistics
import tempfile
import unicodedata
from pathlib import Path

from app.config import RAIZ_PROYECTO, Settings
from app.rag import contexto as modulo_contexto
from app.rag.contexto import armar_contexto
from app.rag.embeddings import crear_embeddings
from app.rag.indice import IndiceVectorial
from app.rag.tokens import estimar_tokens
from scripts.calibrar import ruta_json

BANCO = RAIZ_PROYECTO / "tests" / "evaluacion" / "banco_30.csv"

# Por pregunta, una lista de datos esenciales; cada dato es una lista de
# expresiones regulares que deben aparecer todas en el contexto.
ESENCIALES: dict[str, list[list[str]]] = {
    "N01": [[r"proceso de graduacion"], [r"pdf unico|archivo pdf unico|un solo pdf|unico archivo pdf"],
            [r"cedula", r"paysa", r"saber pro"]],
    "N02": [[r"ajuste extemporaneo de matricula"], [r"comite de asuntos estudiantiles de pregrados presenciales"]],
    "N03": [[r"cancelacion curso\(s\) por 3ra vez"]],
    "N04": [[r"cancelacion extemporanea de curso"], [r"notas a la fecha"]],
    "N05": [[r"consejo academico"], [r"paysa"]],
    "N06": [[r"10 dias habiles"], [r"vicedecanato"]],
    "N07": [[r"exoneracion de prerrequisito"], [r"carta de justificacion", r"historial academico"]],
    "N08": [[r"refrendar"], [r"microcurriculo|programas analiticos", r"certificado"]],
    "N09": [[r"matricula extemporanea"], [r"codigo, nombre y grupo"]],
    "N10": [[r"27 creditos"], [r"carta de solicitud", r"materias faltantes"]],
    "N11": [[r"menos de 8 creditos"], [r"pensum cerrado"]],
    "N12": [[r"acuerdo de homologacion", r"carta de aceptacion"], [r"internacionalingenieria@udea\.edu\.co"]],
    "N13": [[r"validacion english pifle"]],
    "N14": [[r"comite de carrera"], [r"bloque 21"], [r"16:00"]],
    "N15": [[r"dos \(2\) dias habiles|2 dias habiles"], [r"bit\.ly/viceing"]],
    "N16": [[r"incompleto curso o semestre"], [r"no mayor a 6 meses"]],
    "N17": [[r"validable"], [r"no tener matriculada"]],
    "N18": [[r"7 dias", r"aval"], [r"consejo academico"]],
    "A01": [[r"portal universitario", r"40"], [r"cancelacion extemporanea de curso"]],
    "A02": [[r"matricula extemporanea"], [r"ajuste extemporaneo de matricula"]],
    "A03": [[r"supletorio"], [r"incompleto"]],
    "A04": [[r"por el portal antes del 40", r"paysa"], [r"cancelacion extemporanea de semestre", r"consejo academico"]],
    "R04": [[r"definitiva"]],
}
SOLO_CONDUCTA = {"R01", "R02", "R03"}


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.casefold())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def datos_faltantes(pid: str, contexto: str) -> list[int]:
    """Números (1, 2, ...) de los datos esenciales que no están en el contexto."""
    t = normalizar(contexto)
    return [k for k, dato in enumerate(ESENCIALES[pid], 1) if not all(re.search(e, t) for e in dato)]


def leer_banco(ruta: Path = BANCO) -> list[dict]:
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))
    for r in filas:
        r["aceptadas"] = [r["ficha_esperada"]] + [
            x.strip() for x in (r.get("fichas_alternativas") or "").split(";") if x.strip()]
    return filas


def fichas_proactivas(indice: IndiceVectorial, pregunta: str, densas: list[str], factor: float,
                      maximo: int = 2) -> list[str]:
    """Fichas léxicas fuera del vectorial que puntúan >= factor × la mejor vectorial."""
    if factor <= 0:
        return []
    puntajes = indice._indice_lexico().puntuar(pregunta)
    referencia = max((puntajes.get(f, 0.0) for f in densas), default=0.0)
    if referencia <= 0:
        return []
    candidatas = sorted(((p, f) for f, p in puntajes.items()
                         if f not in densas and p >= factor * referencia), reverse=True)
    return [f for _, f in candidatas[:maximo]]


def _titulo_a_id(indice: IndiceVectorial, fichas: list[str]) -> dict[str, str]:
    salida = {}
    for f in fichas:
        secciones = indice.secciones_de_ficha(f)
        if secciones:
            salida[secciones[0].titulo] = f
    return salida


def fichas_del_contexto(contexto: str, titulos: dict[str, str]) -> list[str]:
    """Ids de las fichas en el orden en que aparecen en el contexto."""
    orden: list[str] = []
    for bloque in contexto.split("\n\n---\n\n"):
        fid = titulos.get(bloque.split("\n", 1)[0])
        if fid and fid not in orden:
            orden.append(fid)
    return orden


def medir(indice: IndiceVectorial, s: Settings, filas: list[dict], presupuesto: int,
          max_fichas: int, proactivo: float) -> dict[str, dict]:
    anterior = modulo_contexto.MAX_FICHAS
    modulo_contexto.MAX_FICHAS = max_fichas
    try:
        titulos = _titulo_a_id(indice, sorted({f.ficha_id for r in filas for f in indice.buscar(r["pregunta"], 40)}
                                              | {a for r in filas for a in r["aceptadas"]}))
        res: dict[str, dict] = {}
        for r in filas:
            pid, pregunta = r["id"], r["pregunta"]
            encontrados = [x for x in indice.buscar(pregunta, s.rag_top_k) if x.distancia <= s.rag_max_distance]
            if not encontrados:
                res[pid] = {"fuera": True, "estado": "ok" if pid.startswith("F") else "falta"}
                continue
            densas = list(dict.fromkeys(x.ficha_id for x in sorted(encontrados, key=lambda x: x.distancia)))
            proactivas = fichas_proactivas(indice, pregunta, densas, proactivo)
            c1 = "\n\n---\n\n".join(armar_contexto(encontrados, indice, presupuesto, pregunta=pregunta,
                                                   prioritarias=proactivas or None))
            rescate = indice.fichas_lexicas(pregunta, densas + proactivas)
            c2 = ("\n\n---\n\n".join(armar_contexto(encontrados, indice, presupuesto, pregunta=pregunta,
                                                    prioritarias=rescate)) if rescate else "")
            if c2 == c1:
                c2 = ""
            d = {"fuera": False, "proactivas": proactivas, "rescate": rescate,
                 "tokens1": estimar_tokens(c1), "tokens2": estimar_tokens(c2) if c2 else 0,
                 "fichas1": fichas_del_contexto(c1, titulos), "fichas2": fichas_del_contexto(c2, titulos)}
            if pid in SOLO_CONDUCTA or pid.startswith("F"):
                d["estado"] = "ok" if not pid.startswith("F") else "falta"
                d["usado"] = "1.ª"
            else:
                f1 = datos_faltantes(pid, c1)
                f2 = datos_faltantes(pid, c2) if c2 else None
                d.update(faltan1=f1, faltan2=f2)
                d["estado"] = "ok" if not f1 else ("rescate" if f2 == [] else "falta")
                d["usado"] = "rescate" if (f1 and f2 == []) else "1.ª"
            usadas = d["fichas2"] if d["usado"] == "rescate" else d["fichas1"]
            puestos = [usadas.index(a) + 1 for a in r["aceptadas"] if a in usadas]
            d["puesto"] = min(puestos) if puestos else None
            res[pid] = d
        return res
    finally:
        modulo_contexto.MAX_FICHAS = anterior


def crear_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proveedor", choices=["onnx", "local", "mock"], required=True)
    ap.add_argument("--presupuesto", type=int, nargs="+", default=[1500],
                    help="RAG_CONTEXTO_MAX_TOKENS a medir.")
    ap.add_argument("--max-fichas", type=int, nargs="+", default=[modulo_contexto.MAX_FICHAS],
                    help="Fichas candidatas en el contexto (MAX_FICHAS).")
    ap.add_argument("--proactivo", type=float, nargs="+", default=[0.0],
                    help="Factor del rescate léxico proactivo (0 = apagado).")
    ap.add_argument("--json", type=ruta_json, help="Guarda el detalle en este .json dentro de data/.")
    return ap


def main() -> None:
    import json

    args = crear_parser().parse_args()
    logging.basicConfig(level=logging.WARNING)
    filas = leer_banco()
    with tempfile.TemporaryDirectory(prefix="esenciales_", ignore_cleanup_errors=True) as tmp:
        s = Settings(_env_file=None, embeddings_provider=args.proveedor,  # pyright: ignore[reportCallIssue]
                     chroma_path=Path(tmp) / "chroma")
        embeddings = crear_embeddings(s)
        indice = IndiceVectorial(s, embeddings)
        indice.reconstruir()
        combinaciones = list(itertools.product(args.presupuesto, args.max_fichas, args.proactivo))
        resultados = {(p, m, f): medir(indice, s, filas, p, m, f) for p, m, f in combinaciones}
        del indice

    def nombre(c):
        return f"{c[0]} tokens · {c[1]} fichas · proactivo {c[2]:g}"

    print(f"\n=== {embeddings.nombre} · umbral {s.rag_max_distance} · banco de {len(filas)} preguntas")
    print(f"{'combinación':40} {'datos ok':>8} {'en 1.ª':>6} {'rescate':>7} {'principal ok':>12} {'ctx medio':>9}")
    for c, res in resultados.items():
        ok = sum(d["estado"] != "falta" for d in res.values())
        resc = sum(d["estado"] == "rescate" for d in res.values())
        principal = sum(d.get("puesto") == 1 for d in res.values())
        ctx = statistics.mean(d["tokens1"] for d in res.values() if not d["fuera"])
        print(f"{nombre(c):40} {ok:>5}/{len(filas)} {ok - resc:>6} {resc:>7} {principal:>12} {ctx:>9.0f}")

    ref = combinaciones[0]
    print(f"\nPreguntas que cambian respecto a «{nombre(ref)}» (estado · puesto de la ficha esperada):")
    for r in filas:
        pid = r["id"]
        celdas = [(res[pid]["estado"], res[pid].get("puesto")) for res in resultados.values()]
        if len(set(celdas)) > 1:
            print(f"  {pid}: " + " | ".join(f"{e}·{p or '-'}" for e, p in celdas))
    print("Columnas: " + " | ".join(nombre(c) for c in combinaciones))

    if args.json:
        ruta_json(str(args.json)).write_text(json.dumps(
            {nombre(c): res for c, res in resultados.items()}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
