"""
Ranking léxico (BM25) sobre los mismos fragmentos del índice vectorial.

¿Para qué? El modelo de embeddings es pequeño y promedia la frase completa:
cuando la pregunta mezcla vocabulario de trámite ("¿qué pasos sigo en SSOFI?")
con palabras que no están en ninguna ficha (el nombre de una materia, de otra
universidad), el vector se aleja de la ficha correcta y aterriza en cualquier
sección genérica de "pasos para radicar".

BM25 no entiende de sinónimos, pero sí premia las palabras poco frecuentes que
la ficha correcta contiene. Por eso no se usa solo: se usa para PROPONER
fichas adicionales cuando el vectorial ya demostró que la pregunta es del
dominio (ver `IndiceVectorial.fichas_lexicas`).

Sin dependencias externas: son 500 fragmentos, cabe en memoria y se construye
una sola vez por índice.
"""

import math
import re
import unicodedata
from collections import Counter

# Palabras vacías del español que no distinguen una ficha de otra. Se comparan
# sin tildes y en minúsculas.
_VACIAS = frozenset("""
a al algo algun alguna algunas alguno algunos ante antes aquel aquella con
contra cual cuales cuando de del desde donde dos el ella ellas ellos en entre
era eres es esa esas ese eso esos esta estaba estan estar estas este esto
estos fue fueron ha habe haber habia han hasta la las le les lo los mas me mi
mis mucho muy no nos o os otra otro para pero poco por porque que quien se
sea segun ser si sin sobre su sus tambien te tengo tiene tienen tu tus un una
unas uno unos usted ustedes y ya yo
""".split())

_TOKEN = re.compile(r"[a-z0-9]+")
K1 = 1.5
B = 0.75


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes (igual que la clasificación de secciones)."""
    t = unicodedata.normalize("NFD", texto.casefold())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def palabras(texto: str) -> list[str]:
    """Términos con los que se compara: sin vacías, sin números sueltos."""
    return [p for p in _TOKEN.findall(normalizar(texto))
            if p not in _VACIAS and len(p) > 2]


class IndiceLexico:
    """BM25 Okapi sobre una lista de textos y su ficha de origen."""

    def __init__(self, textos: list[str], fichas: list[str]) -> None:
        if len(textos) != len(fichas):
            raise ValueError("textos y fichas deben tener el mismo tamaño")
        self._fichas = fichas
        self._frecuencias = [Counter(palabras(t)) for t in textos]
        self._largos = [sum(c.values()) for c in self._frecuencias]
        self._largo_medio = (sum(self._largos) / len(textos)) if textos else 0.0

        documento_frecuencia: Counter[str] = Counter()
        for c in self._frecuencias:
            documento_frecuencia.update(c.keys())
        n = len(textos)
        self._idf = {
            palabra: math.log(1 + (n - df + 0.5) / (df + 0.5))
            for palabra, df in documento_frecuencia.items()
        }

    def __len__(self) -> int:
        return len(self._fichas)

    def puntuar(self, consulta: str) -> dict[str, float]:
        """Puntaje de cada ficha: el de su mejor fragmento."""
        terminos = palabras(consulta)
        mejor: dict[str, float] = {}
        if not terminos or not self._fichas:
            return mejor
        idf = self._idf
        for i, frecuencias in enumerate(self._frecuencias):
            largo = self._largos[i]
            puntaje = 0.0
            for termino in terminos:
                f = frecuencias.get(termino, 0)
                if not f:
                    continue
                puntaje += idf.get(termino, 0.0) * (f * (K1 + 1)) / (
                    f + K1 * (1 - B + B * largo / (self._largo_medio or 1))
                )
            if puntaje > mejor.get(self._fichas[i], 0.0):
                mejor[self._fichas[i]] = puntaje
        return mejor
