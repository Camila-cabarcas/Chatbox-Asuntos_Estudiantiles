"""
scripts/medir_esenciales.py: los marcadores corresponden al banco, la
búsqueda de datos esenciales funciona y la salida solo se escribe en data/.
"""

import argparse

import pytest

from app.config import RAIZ_PROYECTO
from scripts.medir_esenciales import (ESENCIALES, SOLO_CONDUCTA, crear_parser, datos_faltantes,
                                      fichas_proactivas, leer_banco)


def test_marcadores_cubren_el_banco():
    ids = {r["id"] for r in leer_banco()}
    assert set(ESENCIALES) <= ids
    # Todas las preguntas que no son fuera de alcance ni de pura conducta
    # tienen marcadores; si se agrega una al banco, hay que escribirlos.
    assert {i for i in ids if not i.startswith("F")} - SOLO_CONDUCTA == set(ESENCIALES)


def test_datos_faltantes_ignora_tildes_y_mayusculas():
    contexto = "Debes radicar en SSOFI. El Consejo Académico decide. Paz y salvo de PAYSA."
    assert datos_faltantes("N05", contexto) == []
    assert datos_faltantes("N05", "Lo decide el Consejo Académico.") == [2]


def test_un_dato_con_varias_expresiones_exige_todas():
    # N10, dato 2: carta de solicitud Y constancia de materias faltantes.
    assert datos_faltantes("N10", "Hasta 27 créditos. Carta de solicitud.") == [2]
    assert datos_faltantes("N10", "Hasta 27 créditos. Carta de solicitud y materias faltantes.") == []


def test_proactivo_apagado_no_consulta_el_indice():
    class SinIndice:
        def _indice_lexico(self):
            raise AssertionError("con factor 0 no debe puntuar")
    assert fichas_proactivas(SinIndice(), "pregunta", ["ficha"], 0) == []  # pyright: ignore[reportArgumentType]


def test_json_solo_dentro_de_data(tmp_path):
    with pytest.raises(SystemExit):
        crear_parser().parse_args(["--proveedor", "mock", "--json", str(tmp_path / "x.json")])
    args = crear_parser().parse_args(["--proveedor", "mock", "--json", str(RAIZ_PROYECTO / "data" / "x.json")])
    assert args.json.parent == (RAIZ_PROYECTO / "data").resolve()


def test_valores_por_defecto():
    args = crear_parser().parse_args(["--proveedor", "onnx"])
    assert (args.presupuesto, args.max_fichas, args.proactivo) == ([1800], [4], [0.0])
    with pytest.raises(SystemExit):
        crear_parser().parse_args(["--proveedor", "otro"])
    assert isinstance(crear_parser(), argparse.ArgumentParser)
