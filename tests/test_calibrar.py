"""
Validación de los argumentos de scripts/calibrar.py: el CSV debe estar
dentro del proyecto, el JSON dentro de data/ y el modelo debe ser un
identificador de Hugging Face, no una ruta.
"""

import argparse
from collections import Counter

import pytest

from app.config import RAIZ_PROYECTO
from app.rag.fichas import cargar_fichas
from scripts.calibrar import (CSV_POR_DEFECTO, crear_parser, id_modelo, leer_csv, resumen_por_ficha, ruta_csv,
                              ruta_json)

CSV_COBERTURA = RAIZ_PROYECTO / "tests" / "calibracion" / "cobertura.csv"


def test_csv_fuera_del_proyecto_se_rechaza(tmp_path):
    afuera = tmp_path / "preguntas.csv"
    afuera.write_text("pregunta,ficha_esperada,dentro_alcance\n", encoding="utf-8")
    with pytest.raises(argparse.ArgumentTypeError, match="dentro de"):
        ruta_csv(str(afuera))


def test_csv_con_ruta_relativa_que_sale_del_proyecto_se_rechaza():
    with pytest.raises(argparse.ArgumentTypeError, match="dentro de"):
        ruta_csv(str(RAIZ_PROYECTO / "tests" / ".." / ".." / "preguntas.csv"))


@pytest.mark.parametrize("nombre", [".env", "README.md", ".env.example"])
def test_csv_debe_tener_extension_csv(nombre):
    with pytest.raises(argparse.ArgumentTypeError, match=r"\.csv"):
        ruta_csv(str(RAIZ_PROYECTO / nombre))


def test_csv_del_proyecto_se_acepta():
    assert ruta_csv(str(CSV_POR_DEFECTO)) == CSV_POR_DEFECTO.resolve()


def test_leer_csv_valida_aunque_no_pase_por_argparse(tmp_path):
    afuera = tmp_path / "preguntas.csv"
    afuera.write_text("pregunta,ficha_esperada,dentro_alcance\n", encoding="utf-8")
    with pytest.raises(argparse.ArgumentTypeError):
        leer_csv(afuera)


def test_la_linea_de_comandos_rechaza_un_csv_fuera_del_proyecto(tmp_path, capsys):
    afuera = tmp_path / "preguntas.csv"
    afuera.write_text("pregunta,ficha_esperada,dentro_alcance\n", encoding="utf-8")
    with pytest.raises(SystemExit) as salida:
        crear_parser().parse_args(["--proveedor", "mock", "--csv", str(afuera)])
    assert salida.value.code == 2
    assert "debe estar dentro de" in capsys.readouterr().err


def test_json_solo_dentro_de_data(tmp_path):
    with pytest.raises(argparse.ArgumentTypeError, match="dentro de"):
        ruta_json(str(tmp_path / "resultado.json"))
    with pytest.raises(argparse.ArgumentTypeError, match="dentro de"):
        ruta_json(str(RAIZ_PROYECTO / "resultado.json"))  # en el proyecto pero fuera de data/
    with pytest.raises(argparse.ArgumentTypeError, match=r"\.json"):
        ruta_json(str(RAIZ_PROYECTO / "data" / ".env"))
    assert ruta_json(str(RAIZ_PROYECTO / "data" / "calibracion.json")).parent == (RAIZ_PROYECTO / "data").resolve()


@pytest.mark.parametrize("valor", ["C:/modelos/x", "../modelos/x", "/tmp/x", "modelos\\x", "org/../x", "solo-nombre"])
def test_modelo_debe_ser_un_identificador_y_no_una_ruta(valor):
    with pytest.raises(argparse.ArgumentTypeError):
        id_modelo(valor)


def test_modelo_valido_se_acepta():
    assert id_modelo("sentence-transformers/paraphrase-multilingual-mpnet-base-v2")


# --- Columnas opcionales y resumen por ficha ---------------------------------

def test_csv_sin_dentro_alcance_cuenta_todo_como_dentro():
    filas = leer_csv(CSV_COBERTURA)
    assert filas and all(r["dentro"] and r["tipo"] == "dentro" for r in filas)


def test_fichas_alternativas_se_suman_a_la_esperada():
    filas = {r["pregunta"]: r for r in leer_csv(CSV_COBERTURA)}
    r = filas["estoy matriculado pero necesito retirar un curso y ya pasó la semana de ajustes"]
    assert r["aceptadas"] == ["ajuste-extemporaneo-matricula", "ajustes-especiales-matricula",
                              "cancelacion-extemporanea-cursos", "cancelaciones-reglamentarias-especiales"]
    assert filas["¿tengo que haber presentado el Saber Pro para poder graduarme?"]["aceptadas"] == [
        "acto-de-graduacion"]


def test_csv_original_no_tiene_alternativas():
    assert all(len(r["aceptadas"]) == 1 for r in leer_csv(CSV_POR_DEFECTO))


def test_cobertura_tiene_tres_preguntas_por_ficha():
    conteo = Counter(r["ficha_esperada"] for r in leer_csv(CSV_COBERTURA))
    ids = {f.id for f in cargar_fichas(RAIZ_PROYECTO / "fichas")}
    assert set(conteo) == ids
    assert set(conteo.values()) == {3}
    for r in leer_csv(CSV_COBERTURA):
        assert set(r["aceptadas"]) <= ids


def test_resumen_por_ficha():
    def d(ficha, uno, top, umbral, ctx, dentro=True):
        return {"esperada": ficha, "dentro": dentro, "acierto_1": uno, "acierto_top": top,
                "pasa_umbral": umbral, "en_contexto": ctx}
    detalle = [d("b", True, True, True, True), d("b", False, True, False, False),
               d("a", False, False, True, False), d("", False, False, True, False, dentro=False)]
    assert resumen_por_ficha(detalle) == [
        {"ficha": "a", "preguntas": 1, "acierto_1": 0, "acierto_top": 0, "fuera_umbral": 0, "sin_contexto": 1},
        {"ficha": "b", "preguntas": 2, "acierto_1": 1, "acierto_top": 2, "fuera_umbral": 1, "sin_contexto": 1},
    ]
