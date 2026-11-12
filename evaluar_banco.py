import csv
import json
import time
from datetime import datetime
from pathlib import Path

import httpx

# 45 s entre preguntas: ~1,3 preguntas/min, debajo del límite por minuto del
# plan gratuito incluso con el contexto lleno (~4 500 tokens por petición).
ESPERA = 45
# Si el modelo devuelve el mensaje de error, se reintenta la misma pregunta.
REINTENTOS = 2
ESPERA_ERROR = 70

filas = list(
    csv.DictReader(open("tests/evaluacion/banco_30.csv", encoding="utf-8-sig"))
)
salida = []

for i, f in enumerate(filas, 1):
    for intento in range(1, REINTENTOS + 1):
        try:
            res = httpx.post(
                "http://127.0.0.1:8000/api/chat",
                json={"pregunta": f["pregunta"]},
                timeout=180,
            )

            # Si el servidor responde con un error HTTP (500, 429, 404, etc.)
            if res.status_code != 200:
                print(
                    f"[{i}] Error en {f['id']} (Status {res.status_code}): {res.text}"
                )
                raise SystemExit(1)

            d = res.json()
            fallo = "no pude generar" in d.get("respuesta", "")

            if fallo and intento < REINTENTOS:
                print(f"{i} {f['id']}: sin respuesta del modelo, "
                      f"reintento {intento + 1} en {ESPERA_ERROR} s")
                time.sleep(ESPERA_ERROR)
                continue

            salida.append({**f, **d})
            print(i, f["id"], "fuera_de_alcance=", d.get("fuera_de_alcance"),
                  "" if not fallo else "(FALLO DEL MODELO)")
            break

        except httpx.RequestError as exc:
            print(
                f"[{i}] Error de conexión al servidor en la pregunta {f['id']}: {exc}"
            )
            raise SystemExit(1)
        except json.JSONDecodeError:
            print(
                f"[{i}] La respuesta para {f['id']} no vino en formato JSON válido. "
                f"Respuesta recibida: {res.text}"
            )
            raise SystemExit(1)

    time.sleep(ESPERA)

if salida:
    Path("data").mkdir(exist_ok=True)
    ruta = Path(f"data/evaluacion_{datetime.now():%Y-%m-%d_%H%M}.json")
    ruta.write_text(
        json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Guardado en", ruta)
else:
    print("No se registraron respuestas válidas. Revisa la terminal del servidor.")
