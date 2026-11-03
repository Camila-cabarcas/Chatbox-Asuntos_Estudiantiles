"""Reevalúa solo algunas preguntas de un JSON y mezcla las respuestas nuevas.

Sin argumentos: repite las que quedaron sin respuesta del modelo.
Con --ids: repite solo esas preguntas (las que cambiaron de contexto).

Uso:
    python reevaluar_fallos.py
    python reevaluar_fallos.py --ids N15 A02
    python reevaluar_fallos.py data/evaluacion_2026-11-01_1839.json --ids N15 A02
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import httpx

URL = "http://127.0.0.1:8000/api/chat"
# Groq rechaza la llamada cuando se agota el tope diario de tokens; esperar 90 s
# no lo repone, pero sí cubre los 429 por minuto, que sí se recuperan solos.
ESPERA_ERROR = 90
INTENTOS = 2
ESPERA_ENTRE = 45
FRASE_ERROR = "no pude generar"


def ruta_entrada(indicada: str | None) -> Path:
    if indicada:
        return Path(indicada)
    return sorted(Path("data").glob("evaluacion_*.json"))[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("json", nargs="?", help="archivo de evaluación de partida")
    ap.add_argument("--ids", nargs="*", help="IDs a repetir (por defecto, las fallidas)")
    args = ap.parse_args()

    ruta = ruta_entrada(args.json)
    datos = json.loads(ruta.read_text(encoding="utf-8"))

    if args.ids:
        objetivo = [i for i, d in enumerate(datos) if d["id"] in set(args.ids)]
        faltan = set(args.ids) - {datos[i]["id"] for i in objetivo}
        if faltan:
            raise SystemExit(f"No están en el JSON: {sorted(faltan)}")
    else:
        objetivo = [i for i, d in enumerate(datos)
                    if FRASE_ERROR in d.get("respuesta", "")]

    ids = [datos[i]["id"] for i in objetivo]
    print(f"{ruta.name}: {len(ids)} pregunta(s) -> {ids}")
    if not objetivo:
        print("Nada que reevaluar.")
        return

    for n, i in enumerate(objetivo, 1):
        d = None
        for intento in range(1, INTENTOS + 1):
            print(f"[{n}/{len(objetivo)}] {datos[i]['id']} intento {intento}/{INTENTOS}")
            res = httpx.post(URL, json={"pregunta": datos[i]["pregunta"]}, timeout=180)
            if res.status_code != 200:
                print(f"  el servidor respondió {res.status_code}: {res.text[:200]}")
                raise SystemExit(1)
            d = res.json()
            if FRASE_ERROR not in d.get("respuesta", ""):
                break
            if intento < INTENTOS:
                print(f"  sin respuesta del modelo, espero {ESPERA_ERROR} s")
                time.sleep(ESPERA_ERROR)

        datos[i] = {**datos[i], **d}
        ok = FRASE_ERROR not in d.get("respuesta", "")
        print(f"  {'OK' if ok else 'FALLO'} "
              f"({len(d.get('respuesta', ''))} caracteres)")
        if n < len(objetivo):
            time.sleep(ESPERA_ENTRE)

    salida = ruta.with_name(f"{ruta.stem}_re{datetime.now():%H%M}.json")
    salida.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    siguen = [d["id"] for d in datos if FRASE_ERROR in d.get("respuesta", "")]
    print("Guardado en", salida, "| siguen sin respuesta:", siguen or "ninguna")


if __name__ == "__main__":
    main()
