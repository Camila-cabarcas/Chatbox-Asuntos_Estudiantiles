from app.utils.privacidad import enmascarar


def test_enmascara_documento_telefono_y_correo():
    t = enmascarar("Soy CC 1.036.456.789, cel 300 123 4567, correo ana.p@udea.edu.co")
    assert "1.036" not in t and "4567" not in t and "@" not in t
    assert t.count("[número]") == 2 and "[correo]" in t


def test_no_toca_numeros_cortos():
    assert enmascarar("Matricular menos de 8 créditos en 2026") == \
        "Matricular menos de 8 créditos en 2026"
