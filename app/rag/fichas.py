"""
Lectura de las fichas (base de conocimiento) y división en fragmentos.

Cada ficha es un archivo .md en la carpeta fichas/ con:
  - un encabezado YAML entre '---' (id, titulo, fuentes, preguntas_ejemplo...)
  - secciones que empiezan con '## '

De cada ficha salen dos cosas:
  - Secciones completas: lo que recibe el modelo de lenguaje como contexto.
  - Fragmentos de búsqueda: piezas pequeñas que caben en el límite del
    modelo de embeddings (que descarta en silencio lo que lo supere):
      * cada pregunta de preguntas_ejemplo es un fragmento propio;
      * cada sección se divide por párrafos o elementos de lista y, si hace
        falta, por líneas o frases. Nunca se parte una frase.
    Todos empiezan con el título de la ficha y el de la sección, para que
    cada fragmento se entienda solo.

Los archivos que empiezan con '_' (como _plantilla.md) se ignoran.

Una ficha mal escrita NO detiene el sistema: se registra una advertencia y
se omite, para que el resto del chatbot siga funcionando.
"""

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.rag.tokens import estimar_tokens

log = logging.getLogger(__name__)

CAMPOS_OBLIGATORIOS = ("id", "titulo", "fuentes")
SECCION_PREGUNTAS = "Preguntas frecuentes"
LIMITE_POR_DEFECTO = 128
_ENCABEZADO = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
# Elemento de lista de primer nivel, también dentro de una cita ("> - ...").
_ELEMENTO = re.compile(r"^(>\s*)?(\d+\.|[-*])\s")
# Fin de frase: . ! ? seguido de espacio y de algo que empieza otra frase.
_FIN_DE_FRASE = re.compile(r"(?<=[.!?])\s+(?=[¿¡\"'(*A-ZÁÉÍÓÚÑ0-9])")

Contador = Callable[[str], int]


@dataclass
class Fragmento:
    """Pieza pequeña que se convierte en vector para buscar."""
    id: str
    texto: str
    ficha_id: str
    titulo: str
    seccion: str
    url: str
    tipo: str = "seccion"   # "seccion" o "pregunta"
    seccion_id: str = ""    # sección completa a la que pertenece ("" en preguntas)


@dataclass
class Seccion:
    """Sección completa de una ficha: es lo que recibe el modelo de lenguaje."""
    id: str
    ficha_id: str
    titulo: str
    nombre: str
    url: str
    cuerpo: str

    @property
    def texto(self) -> str:
        return f"{self.titulo}\n{self.nombre}\n{self.cuerpo}"


@dataclass
class Ficha:
    id: str
    titulo: str
    url: str
    cuerpo: str
    preguntas_ejemplo: list[str] = field(default_factory=list)
    archivo: str = ""


def leer_ficha(ruta: Path) -> Ficha | None:
    contenido = ruta.read_text(encoding="utf-8")
    m = _ENCABEZADO.match(contenido)
    if not m:
        log.warning("Ficha omitida (sin encabezado '---'): %s", ruta.name)
        return None
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        log.warning("Ficha omitida (encabezado YAML inválido) %s: %s", ruta.name, e)
        return None

    faltan = [c for c in CAMPOS_OBLIGATORIOS if not meta.get(c)]
    if faltan:
        log.warning("Ficha omitida %s: faltan campos %s", ruta.name, faltan)
        return None

    fuentes = meta["fuentes"]
    url = fuentes[0].get("url", "") if isinstance(fuentes, list) and fuentes else ""
    return Ficha(
        id=str(meta["id"]),
        titulo=str(meta["titulo"]),
        url=url,
        cuerpo=m.group(2).strip(),
        preguntas_ejemplo=[str(p) for p in meta.get("preguntas_ejemplo") or []],
        archivo=ruta.name,
    )


def secciones_de(ficha: Ficha) -> list[Seccion]:
    secciones: list[Seccion] = []
    # Divide por títulos de nivel 2 ('## ').
    partes = re.split(r"^##\s+", ficha.cuerpo, flags=re.MULTILINE)
    for i, parte in enumerate(p for p in partes if p.strip()):
        lineas = parte.strip().splitlines()
        # Las líneas '---' son separadores visuales, no contenido.
        cuerpo = "\n".join(ln for ln in lineas[1:] if ln.strip() != "---").strip()
        cuerpo = re.sub(r"\n{3,}", "\n\n", cuerpo)
        if not cuerpo:
            continue
        secciones.append(Seccion(
            id=f"{ficha.id}::{i}", ficha_id=ficha.id, titulo=ficha.titulo,
            nombre=lineas[0].strip(), url=ficha.url, cuerpo=cuerpo,
        ))
    return secciones


# --------------------------------------------------------------------------- #
# Troceado de secciones
# --------------------------------------------------------------------------- #

def _bloques(cuerpo: str) -> list[list[str]]:
    """Párrafos y elementos de lista de primer nivel (con sus sub-elementos)."""
    bloques: list[list[str]] = []
    actual: list[str] = []
    for linea in cuerpo.splitlines():
        linea = linea.rstrip()
        if linea.strip() in ("", ">"):
            if actual:
                bloques.append(actual)
                actual = []
            continue
        if _ELEMENTO.match(linea) and actual:
            bloques.append(actual)
            actual = []
        actual.append(linea)
    if actual:
        bloques.append(actual)
    return bloques


def _unir(piezas: list[str]) -> str:
    """Une piezas por líneas sin repetir una línea ya incluida (la línea madre
    y el solapamiento pueden traer la misma línea dos veces)."""
    vistas: set[str] = set()
    lineas: list[str] = []
    for pieza in piezas:
        for linea in pieza.split("\n"):
            if linea not in vistas:
                vistas.add(linea)
                lineas.append(linea)
    return "\n".join(lineas)


def _empacar(piezas: list[str], cabe: Callable[[str], bool], sep: str = "\n") -> list[str]:
    grupos: list[str] = []
    actual: list[str] = []
    for p in piezas:
        if actual and not cabe(sep.join(actual + [p])):
            grupos.append(sep.join(actual))
            actual = []
        actual.append(p)
    if actual:
        grupos.append(sep.join(actual))
    return grupos


def _frases(linea: str, cabe: Callable[[str], bool]) -> list[str]:
    frases = _FIN_DE_FRASE.split(linea)
    if len(frases) == 1:
        return [linea]  # una sola frase que no cabe: se deja entera
    return _empacar(frases, cabe, sep=" ")


def _unidades(lineas: list[str], cabe: Callable[[str], bool]) -> list[str]:
    """Convierte un bloque en unidades que caben. Si un bloque de varias
    líneas no cabe, su primera línea (la "línea madre", p. ej. "1. Materias
    del núcleo común:") encabeza cada grupo de líneas hijas."""
    texto = "\n".join(lineas)
    if cabe(texto):
        return [texto]
    if len(lineas) == 1:
        return _frases(lineas[0], cabe)

    madre, hijas = lineas[0], [p for h in lineas[1:] for p in _unidades([h], cabe)]
    salida: list[str] = []
    actual: list[str] = []
    madre_sola = False
    for hija in hijas:
        if actual and cabe("\n".join(actual + [hija])):
            actual.append(hija)
            continue
        if actual:
            salida.append("\n".join(actual))
        if cabe(f"{madre}\n{hija}"):
            actual = [madre, hija]
        else:
            # Ni siquiera con la madre cabe: la madre va una vez, sola.
            if not madre_sola:
                salida.extend(_frases(madre, cabe))
                madre_sola = True
            actual = [hija]
    if actual:
        salida.append("\n".join(actual))
    return salida


def _es_introduccion(pieza: str) -> bool:
    """Línea que presenta lo que sigue, como "Regla de Cancelación por 3ra Vez:"."""
    return pieza.split("\n")[-1].rstrip(" *_").endswith(":")


def _partes(unidades: list[str], cabe: Callable[[str], bool], solapamiento: int) -> list[list[str]]:
    partes: list[list[str]] = []
    actual: list[str] = []
    for u in unidades:
        if actual and not cabe(_unir(actual + [u])):
            # Una introducción no cierra una parte: pasa a la siguiente.
            arrastre = [actual.pop()] if len(actual) > 1 and _es_introduccion(actual[-1]) else []
            partes.append(actual)
            previas = actual[-solapamiento:] if solapamiento else []
            actual = []
            for candidato in (previas + arrastre, arrastre, previas):
                if candidato and cabe(_unir(candidato + [u])):
                    actual = candidato
                    break
            if arrastre and arrastre[0] not in actual:
                partes[-1].append(arrastre[0])  # no cupo adelante: se devuelve
        actual.append(u)
    if actual:
        partes.append(actual)
    return partes


def dividir(
    ficha: Ficha,
    contar: Contador = estimar_tokens,
    limite: int = LIMITE_POR_DEFECTO,
    solapamiento: int = 1,
    avisar: bool = True,
) -> list[Fragmento]:
    """`avisar=False` cuando `contar` es solo una estimación: una frase larga
    puede "pasarse" según la estimación y caber en el modelo real."""
    fragmentos: list[Fragmento] = []

    def agregar(id_: str, texto: str, seccion: str, tipo: str, seccion_id: str) -> None:
        n = contar(texto)
        if n > limite:
            log.log(logging.WARNING if avisar else logging.DEBUG,
                    "Fragmento %s supera el límite (%d > %d tokens): tiene una frase "
                    "que no se puede dividir; el modelo leerá solo el comienzo.",
                    id_, n, limite)
        fragmentos.append(Fragmento(
            id=id_, texto=texto, ficha_id=ficha.id, titulo=ficha.titulo,
            seccion=seccion, url=ficha.url, tipo=tipo, seccion_id=seccion_id,
        ))

    for s in secciones_de(ficha):
        cabecera = f"{ficha.titulo}\n{s.nombre}\n"

        def cabe(t: str, cabecera: str = cabecera) -> bool:
            return contar(cabecera + t) <= limite

        unidades = [u for b in _bloques(s.cuerpo) for u in _unidades(b, cabe)]
        for j, parte in enumerate(_partes(unidades, cabe, solapamiento)):
            agregar(f"{s.id}.{j}", cabecera + _unir(parte), s.nombre, "seccion", s.id)

    for k, pregunta in enumerate(ficha.preguntas_ejemplo):
        agregar(f"{ficha.id}::p{k}", f"{ficha.titulo}\n{SECCION_PREGUNTAS}\n{pregunta}",
                SECCION_PREGUNTAS, "pregunta", "")
    return fragmentos


# --------------------------------------------------------------------------- #
# Carga de la carpeta
# --------------------------------------------------------------------------- #

def cargar_fichas(carpeta: Path) -> list[Ficha]:
    if not carpeta.exists():
        log.warning("No existe la carpeta de fichas: %s", carpeta)
        return []
    fichas: list[Ficha] = []
    ids_vistos: set[str] = set()
    for ruta in sorted(carpeta.glob("*.md")):
        if ruta.name.startswith("_"):
            continue
        ficha = leer_ficha(ruta)
        if ficha is None:
            continue
        if ficha.id in ids_vistos:
            log.warning("Ficha omitida %s: el id '%s' está repetido", ruta.name, ficha.id)
            continue
        ids_vistos.add(ficha.id)
        fichas.append(ficha)
    return fichas


def fragmentos_de(
    fichas: list[Ficha],
    contar: Contador = estimar_tokens,
    limite: int = LIMITE_POR_DEFECTO,
    solapamiento: int = 1,
    avisar: bool = True,
) -> list[Fragmento]:
    fragmentos = [f for ficha in fichas
                  for f in dividir(ficha, contar, limite, solapamiento, avisar)]
    log.info("Fichas cargadas: %d | fragmentos: %d", len(fichas), len(fragmentos))
    return fragmentos


def cargar_fragmentos(
    carpeta: Path,
    contar: Contador = estimar_tokens,
    limite: int = LIMITE_POR_DEFECTO,
    solapamiento: int = 1,
    avisar: bool = True,
) -> list[Fragmento]:
    return fragmentos_de(cargar_fichas(carpeta), contar, limite, solapamiento, avisar)
