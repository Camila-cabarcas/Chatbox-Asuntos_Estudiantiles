"""
Lectura de las fichas (base de conocimiento) y división en fragmentos.

Cada ficha es un archivo .md en la carpeta fichas/ con:
  - un encabezado YAML entre '---' (id, titulo, fuentes, preguntas_ejemplo...)
  - secciones que empiezan con '## '

Cada sección se convierte en un fragmento independiente. Los archivos que
empiezan con '_' (como _plantilla.md) se ignoran.

Una ficha mal escrita NO detiene el sistema: se registra una advertencia y
se omite, para que el resto del chatbot siga funcionando.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

CAMPOS_OBLIGATORIOS = ("id", "titulo", "fuentes")
_ENCABEZADO = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


@dataclass
class Fragmento:
    id: str
    texto: str
    ficha_id: str
    titulo: str
    seccion: str
    url: str


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


def dividir(ficha: Ficha) -> list[Fragmento]:
    fragmentos: list[Fragmento] = []
    # Divide por títulos de nivel 2 ('## ').
    partes = re.split(r"^##\s+", ficha.cuerpo, flags=re.MULTILINE)
    for i, parte in enumerate(p for p in partes if p.strip()):
        lineas = parte.strip().splitlines()
        seccion = lineas[0].strip()
        cuerpo = "\n".join(lineas[1:]).strip()
        if not cuerpo:
            continue
        fragmentos.append(Fragmento(
            id=f"{ficha.id}::{i}",
            # El título de la ficha va dentro del texto para que cada
            # fragmento se entienda solo.
            texto=f"{ficha.titulo}\n{seccion}\n{cuerpo}",
            ficha_id=ficha.id, titulo=ficha.titulo, seccion=seccion, url=ficha.url,
        ))
    if ficha.preguntas_ejemplo:
        fragmentos.append(Fragmento(
            id=f"{ficha.id}::preguntas",
            texto=f"{ficha.titulo}\nPreguntas frecuentes sobre este tema:\n"
                  + "\n".join(f"- {p}" for p in ficha.preguntas_ejemplo),
            ficha_id=ficha.id, titulo=ficha.titulo, seccion="Preguntas frecuentes",
            url=ficha.url,
        ))
    return fragmentos


def cargar_fragmentos(carpeta: Path) -> list[Fragmento]:
    if not carpeta.exists():
        log.warning("No existe la carpeta de fichas: %s", carpeta)
        return []
    fragmentos: list[Fragmento] = []
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
        fragmentos.extend(dividir(ficha))
    log.info("Fichas cargadas: %d | fragmentos: %d", len(ids_vistos), len(fragmentos))
    return fragmentos
