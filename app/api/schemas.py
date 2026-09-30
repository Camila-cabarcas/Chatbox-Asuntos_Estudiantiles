"""
Contrato de la API. Es el acuerdo entre frontend y backend: si se cambia
algo aquí, se avisa al equipo y se actualiza docs/acuerdos.md.
"""

from pydantic import BaseModel, Field


class PreguntaIn(BaseModel):
    pregunta: str = Field(..., min_length=2, max_length=1000,
                          examples=["¿Cómo cancelo el semestre?"])


class Fuente(BaseModel):
    titulo: str
    url: str


class RespuestaOut(BaseModel):
    respuesta: str
    fuentes: list[Fuente] = []
    fuera_de_alcance: bool = False
    id_consulta: int | None = Field(
        None, description="Id para valorar la respuesta. None si la BD está deshabilitada.")


class ValoracionIn(BaseModel):
    util: bool


class EstadoOut(BaseModel):
    estado: str
    base_datos: str
    fragmentos_indexados: int
    proveedor_llm: str
    proveedor_embeddings: str
