"""
Contexto para el modelo de lenguaje: "buscar con fragmentos pequeños,
responder con secciones completas".

A partir de los fragmentos encontrados se arma el contexto con secciones
completas, sin repetir y sin pasar de un presupuesto de tokens
(RAG_CONTEXTO_MAX_TOKENS). Cambios respecto a la versión anterior:

  1. Las fichas candidatas (máximo MAX_FICHAS) se ordenan por parecido.
  2. De cada ficha se arma una cola de secciones por prioridad:
       a. la sección que coincidió con la pregunta (si coincidió una sección);
       b. las secciones que pide la INTENCIÓN de la pregunta (documentos,
          plazos, contacto, tipo de solicitud/campos);
       c. "pasos" y "qué es";
       d. "contacto" (solo en la ficha principal);
       e. el resto, en el orden de la ficha.
  3. Se reparte por rondas: la ficha principal recibe CUPO_PRINCIPAL secciones
     por ronda y las demás una. Así entran varias fichas antes de que una sola
     llene el presupuesto.
  4. Opcional (INCLUIR_RELACIONADAS): si una ficha tiene una "vía alternativa"
     (p. ej. cancelación ordinaria vs. extemporánea), la ficha hermana entra
     con baja prioridad y se toma primero su sección de vías/tipos (nunca la
     introducción "¿qué es?"), para que el modelo pueda presentar las dos vías.

Si una sección completa no cabe, se usa en su lugar el fragmento encontrado.
Si no se puede clasificar una sección, el comportamiento es el de antes:
orden de aparición en la ficha.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from app.rag.fichas import Seccion
from app.rag.indice import Resultado
from app.rag.tokens import estimar_tokens

log = logging.getLogger(__name__)

# ----------------------------- Ajustes ------------------------------------
MAX_FICHAS = 4            # fichas candidatas que entran al contexto
CUPO_PRINCIPAL = 2        # secciones por ronda de la ficha mejor rankeada
INCLUIR_RELACIONADAS = True   # ver RELACIONADAS; apágalo para medir por separado

# Pares de trámites que son "vías alternativas" según el reglamento
# (el momento o la situación del estudiante decide cuál aplica). Se definen
# por la lógica del trámite, no por preguntas del banco; si cambian los id de
# las fichas, hay que actualizar esta lista.
_PARES_RELACIONADOS = (
    ("cancelaciones-reglamentarias-especiales", "cancelacion-extemporanea-cursos"),
    ("cancelaciones-reglamentarias-especiales", "cancelacion-extemporanea-semestre"),
    ("matricula-extemporanea", "ajuste-extemporaneo-matricula"),
    ("examen-supletorio", "solicitud-incompletos-academicos"),
)
RELACIONADAS: dict[str, list[str]] = {}
for _a, _b in _PARES_RELACIONADOS:
    RELACIONADAS.setdefault(_a, []).append(_b)
    RELACIONADAS.setdefault(_b, []).append(_a)

# Tipos de sección, según las palabras del encabezado (sin tildes). El orden
# importa: se usa el primer tipo que coincida.
_TIPOS = (
    ("plazos", ("plazo",)),
    ("documentos", ("documento", "anexo", "soporte")),
    ("requisitos", ("requisito",)),
    ("vias", ("tipos de", "opciones", "vias", "modalidades", "formas de",
              "canales de tramitacion")),
    ("pasos", ("paso", "radicar", "radicacion")),
    ("que_es", ("que es",)),
    ("quien", ("quien puede", "quien", "instancia")),
    ("contacto", ("contacto", "canales", "mas informacion", "contingencia")),
)

# Intención de la pregunta -> palabras que la delatan (sin tildes) y tipos de
# sección que conviene traer. Son palabras generales de los trámites, no de
# preguntas concretas.
_INTENCIONES = {
    "documentos": (("que subo", "que tengo que subir", "que anexo", "anexos", "documento",
                    "papeles", "soporte", "adjunt", "que necesito presentar",
                    "que debo presentar", "requisito"),
                   ("documentos", "requisitos", "pasos")),
    "plazos": (("plazo", "cuantos dias", "hasta cuando", "fecha limite", "cuanto tiempo",
                "dias habiles"),
               ("plazos", "requisitos")),
    "contacto": (("correo", "escribo", "telefono", "llamo", "contacto", "donde entrego",
                  "oficina"),
                 ("contacto",)),
    "formulario": (("que escojo", "que selecciono", "que opcion", "tipo de solicitud",
                    "que campos", "que diligencio", "que pongo", "que tramite",
                    "que solicitud"),
                   ("pasos",)),
    "quien": (("quien da", "quien decide", "quien aprueba", "quien autoriza",
               "quien otorga", "quien concede", "aprobacion final"),
              ("quien", "plazos")),
}

_CITA = re.compile(r"\s*\[cite:[^\]]*\]")


class FuenteDeSecciones(Protocol):
    def seccion(self, seccion_id: str) -> Seccion | None: ...

    def secciones_de_ficha(self, ficha_id: str) -> list[Seccion]: ...


@dataclass
class _Item:
    clave: str
    texto: str
    respaldo: str = ""   # fragmento encontrado, por si la sección no cabe


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.casefold())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _limpiar(texto: str) -> str:
    """Quita marcas de citas pegadas en las fichas, p. ej. [cite: 25]."""
    return _CITA.sub("", texto)


def _encabezado(s: Seccion) -> str:
    # `nombre` es el encabezado de la sección; `titulo` es el de la ficha
    # completa y no sirve para clasificarla (lo llevan todas sus secciones).
    for atributo in ("nombre", "encabezado", "titulo"):
        valor = getattr(s, atributo, None)
        if isinstance(valor, str) and valor.strip():
            return _norm(valor)
    for linea in s.texto.splitlines():
        if linea.strip():
            return _norm(linea.strip()[:160])
    return ""


def tipo_seccion(s: Seccion) -> str:
    h = _encabezado(s)
    for tipo, claves in _TIPOS:
        if any(k in h for k in claves):
            return tipo
    return "otra"


def detectar_tipos_pedidos(pregunta: str) -> list[str]:
    """Tipos de sección que la pregunta pide, en orden de prioridad."""
    p = _norm(pregunta)
    tipos: list[str] = []
    for palabras, tipos_seccion in _INTENCIONES.values():
        if any(k in p for k in palabras):
            tipos.extend(t for t in tipos_seccion if t not in tipos)
    return tipos


def _ordenar(todas: list[Seccion], encontradas: list[tuple[str, str]],
             tipos_pedidos: list[str], principal: bool,
             secciones: FuenteDeSecciones, relacionada: bool = False) -> list[_Item]:
    items: list[_Item] = []
    vistos: set[str] = set()
    por_id = {s.id: s for s in todas}

    def agregar(s: Seccion, respaldo: str = "") -> None:
        if s.id not in vistos:
            vistos.add(s.id)
            items.append(_Item(s.id, s.texto, respaldo))

    def por_tipos(tipos: tuple[str, ...] | list[str]) -> None:
        for tipo in tipos:
            for s in todas:
                if tipo_seccion(s) == tipo:
                    agregar(s)

    for seccion_id, fragmento in encontradas:                 # a.
        s = por_id.get(seccion_id) or secciones.seccion(seccion_id)
        if s is not None:
            agregar(s, fragmento)
        elif seccion_id not in vistos:
            vistos.add(seccion_id)
            items.append(_Item(seccion_id, fragmento))
    if relacionada:
        # La ficha hermana entra a aportar la "otra vía": primero la sección
        # que las enumera (tipos/canales/opciones) y nunca la introducción.
        por_tipos(("vias",))
    por_tipos(tipos_pedidos)                                    # b.
    if relacionada:
        por_tipos(("pasos",))                                   # c.
    else:
        por_tipos(("vias", "pasos", "que_es"))                  # c.
    if principal:                                               # d.
        por_tipos(("contacto",))
    for s in todas:                                             # e.
        if relacionada and tipo_seccion(s) == "que_es":
            continue
        agregar(s)
    return items


def armar_contexto(
    resultados: list[Resultado],
    secciones: FuenteDeSecciones,
    max_tokens: int,
    pregunta: str = "",
    prioritarias: list[str] | None = None,
) -> list[str]:
    ordenados = sorted(resultados, key=lambda r: r.distancia)
    # `prioritarias` son fichas que el ranking léxico propone y el vectorial no
    # trajo (ver IndiceVectorial.fichas_lexicas). Van primero porque son la
    # única evidencia de que el trámite preguntado existe en la base.
    fichas = [f for f in (prioritarias or []) if secciones.secciones_de_ficha(f)]
    fichas += [f for f in dict.fromkeys(r.ficha_id for r in ordenados)
               if f not in fichas][:max(0, MAX_FICHAS - len(fichas))]
    if not fichas:
        return []
    tipos_pedidos = detectar_tipos_pedidos(pregunta)

    colas: list[list[_Item]] = []
    # Una ficha que también es "vía alternativa" de otra candidata se trata
    # como relacionada aunque haya entrado por derecho propio: lo que aporta
    # es su sección de vías, no su introducción.
    vinculadas = {f for f in fichas
                  if any(o in fichas for o in RELACIONADAS.get(f, ()))}

    def cola(ficha_id: str, principal: bool, relacionada: bool | None = None) -> list[_Item]:
        todas = list(secciones.secciones_de_ficha(ficha_id) or [])
        encontradas = [(r.seccion_id, r.texto) for r in ordenados
                       if r.ficha_id == ficha_id and r.tipo != "pregunta" and r.seccion_id]
        if not todas:
            # Índice antiguo: el fragmento está indexado pero la ficha ya no
            # está en disco (o nunca expuso secciones). Se usa el fragmento,
            # que es la única evidencia disponible.
            return [_Item(r.id or f"{ficha_id}:{i}", r.texto)
                    for i, r in enumerate(ordenados) if r.ficha_id == ficha_id]
        return _ordenar(todas, encontradas, tipos_pedidos, principal, secciones,
                        relacionada=(ficha_id in vinculadas) if relacionada is None else relacionada)

    colas.append(cola(fichas[0], True))

    # Las vías alternativas de la ficha principal van justo después de ella:
    # si van al final, el presupuesto ya está gastado y su sección de vías
    # (la que explica la otra ruta) no cabe.
    extras: list[str] = []
    if INCLUIR_RELACIONADAS:
        for otra in RELACIONADAS.get(fichas[0], ()):
            if otra not in fichas and otra not in extras:
                extras.append(otra)
        for otra in extras[:2]:
            if secciones.secciones_de_ficha(otra):
                colas.append(cola(otra, False, relacionada=True))

    for ficha_id in fichas[1:]:
        colas.append(cola(ficha_id, False))

    partes: list[str] = []
    usados: list[str] = []
    total = 0

    def agregar(item: _Item) -> bool:
        nonlocal total
        if item.clave in usados:
            return False
        for texto in (item.texto, item.respaldo):
            if not texto:
                continue
            limpio = _limpiar(texto)
            n = estimar_tokens(limpio)
            if total + n <= max_tokens:
                usados.append(item.clave)
                partes.append(limpio)
                total += n
                return True
        return False

    progreso = True
    while progreso:
        progreso = False
        for i, cola in enumerate(colas):
            cupo = CUPO_PRINCIPAL if i == 0 else 1
            for _ in range(cupo):
                while cola:
                    if agregar(cola.pop(0)):
                        progreso = True
                        break

    log.debug("Contexto: fichas=%s pedidos=%s secciones=%s tokens=%d/%d",
              fichas, tipos_pedidos, usados, total, max_tokens)
    return partes