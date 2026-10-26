"""
Estimación de tokens cuando no hay un tokenizador disponible (modo mock y
presupuesto del contexto que recibe el modelo de lenguaje).

En el texto de las fichas hay entre 3,4 y 4,2 caracteres por token del
modelo de embeddings, así que dividir entre 3 sobreestima a propósito: un
fragmento que "cabe" según esta cuenta también cabe en el modelo real.
"""

import math

CARACTERES_POR_TOKEN = 3
TOKENS_ESPECIALES = 2  # inicio y fin de secuencia


def estimar_tokens(texto: str) -> int:
    return math.ceil(len(texto) / CARACTERES_POR_TOKEN) + TOKENS_ESPECIALES
