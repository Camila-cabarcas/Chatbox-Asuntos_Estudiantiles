"""
Protección de datos personales (Ley 1581 de 2012).

El chatbot no pide datos personales, pero un estudiante puede escribirlos
en su pregunta. Antes de enviar la pregunta al modelo de lenguaje o de
guardarla en la base de datos, se enmascaran correos y números largos
(cédulas, teléfonos, números de documento).
"""

import re

_CORREO = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
# 6 o más dígitos, permitiendo separadores: 1.234.567, 300 123 4567, 1234567890
_NUMERO_LARGO = re.compile(r"\b\d(?:[\s.\-]?\d){5,}\b")


def enmascarar(texto: str) -> str:
    texto = _CORREO.sub("[correo]", texto)
    texto = _NUMERO_LARGO.sub("[número]", texto)
    return texto
