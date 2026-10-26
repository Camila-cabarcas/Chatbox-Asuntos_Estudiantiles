"""
Contexto para el modelo de lenguaje: "buscar con fragmentos pequeños,
responder con secciones completas".

A partir de los fragmentos encontrados se arma el contexto con las secciones
completas a las que pertenecen, sin repetir y sin pasar de un presupuesto de
tokens (RAG_CONTEXTO_MAX_TOKENS), en dos pasadas:

  1. Variedad: por cada fragmento, en orden de parecido, se agrega una
     sección: la suya o, si el fragmento es una pregunta de ejemplo, la
     primera sección aún no incluida de esa ficha. Así entran varias fichas
     candidatas antes de que una sola llene el presupuesto.
  2. Relleno: con lo que sobre del presupuesto se agregan las demás
     secciones de las fichas que coincidieron por una pregunta de ejemplo,
     en el orden en que aparecen en la ficha.

Si una sección completa no cabe, se usa en su lugar el fragmento encontrado.
"""

from typing import Protocol

from app.rag.fichas import Seccion
from app.rag.indice import Resultado
from app.rag.tokens import estimar_tokens


class FuenteDeSecciones(Protocol):
    def seccion(self, seccion_id: str) -> Seccion | None: ...

    def secciones_de_ficha(self, ficha_id: str) -> list[Seccion]: ...


def armar_contexto(
    resultados: list[Resultado],
    secciones: FuenteDeSecciones,
    max_tokens: int,
) -> list[str]:
    partes: list[str] = []
    usados: set[str] = set()
    total = 0

    def agregar(clave: str, texto: str) -> bool:
        nonlocal total
        n = estimar_tokens(texto)
        if clave in usados or total + n > max_tokens:
            return False
        usados.add(clave)
        partes.append(texto)
        total += n
        return True

    # 1. Variedad
    fichas_por_pregunta: list[str] = []
    for r in resultados:
        if r.tipo == "pregunta":
            if r.ficha_id not in fichas_por_pregunta:
                fichas_por_pregunta.append(r.ficha_id)
            libres = [s for s in secciones.secciones_de_ficha(r.ficha_id) if s.id not in usados]
            if libres:
                agregar(libres[0].id, libres[0].texto)
            continue
        s = secciones.seccion(r.seccion_id)
        if s is not None and s.id in usados:
            continue
        if s is None or not agregar(s.id, s.texto):
            # Respaldo: el fragmento encontrado. Cuenta como su sección para
            # no repetir el mismo contenido después.
            if agregar(r.id or r.texto, r.texto) and r.seccion_id:
                usados.add(r.seccion_id)

    # 2. Relleno
    for ficha_id in fichas_por_pregunta:
        for s in secciones.secciones_de_ficha(ficha_id):
            agregar(s.id, s.texto)
    return partes
