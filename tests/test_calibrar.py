"""
Validación de los argumentos de scripts/calibrar.py: el CSV debe estar
dentro del proyecto, el JSON dentro de data/ y el modelo debe ser un
identificador de Hugging Face, no una ruta.
"""

import argparse

import pytest

from app.config import RAIZ_PROYECTO
from scripts.calibrar import CSV_POR_DEFECTO, crear_parser, id_modelo, leer_csv, ruta_csv, ruta_json


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
