"""
Operaciones sobre la tabla de consultas. Ningún error de base de datos se
propaga al estudiante: se registra en el log y se devuelve None/False.
"""

import logging

from sqlalchemy.exc import SQLAlchemyError

from app.db.conexion import BaseDeDatos
from app.db.modelos import Consulta

log = logging.getLogger(__name__)


class RepositorioConsultas:
    def __init__(self, db: BaseDeDatos):
        self._db = db

    def registrar(self, **datos) -> int | None:
        if not self._db.disponible:
            return None
        try:
            with self._db.Sesion() as s, s.begin():
                consulta = Consulta(**datos)
                s.add(consulta)
            return consulta.id
        except SQLAlchemyError as e:
            log.error("No se pudo registrar la consulta: %s", type(e).__name__)
            return None

    def valorar(self, id_consulta: int, util: bool) -> bool:
        if not self._db.disponible:
            return False
        try:
            with self._db.Sesion() as s, s.begin():
                consulta = s.get(Consulta, id_consulta)
                if consulta is None:
                    return False
                consulta.util = util
            return True
        except SQLAlchemyError as e:
            log.error("No se pudo guardar la valoración: %s", type(e).__name__)
            return False
