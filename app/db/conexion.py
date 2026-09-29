"""
Conexión a PostgreSQL con SQLAlchemy.

Si la base de datos no está disponible (Docker apagado, credenciales mal
escritas), el chatbot NO se cae: sigue respondiendo y solo deja de registrar
consultas. El estado se ve en GET /api/health.
"""

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db.modelos import Base

log = logging.getLogger(__name__)


class BaseDeDatos:
    def __init__(self, settings: Settings):
        self.estado = "deshabilitada"
        self._engine: Engine | None = None
        self.Sesion: sessionmaker | None = None
        if not settings.db_enabled:
            log.info("Base de datos deshabilitada (DB_ENABLED=false).")
            return
        try:
            self._engine = create_engine(
                settings.database_url.get_secret_value(),
                pool_pre_ping=True,        # detecta conexiones caídas
                pool_size=5, max_overflow=5,
                connect_args={"connect_timeout": 5},
            )
            with self._engine.connect() as c:
                c.execute(text("SELECT 1"))
            # Crea las tablas si no existen. Para un prototipo es suficiente;
            # en un sistema mayor se usarían migraciones (Alembic).
            Base.metadata.create_all(self._engine)
            self.Sesion = sessionmaker(bind=self._engine, expire_on_commit=False)
            self.estado = "ok"
            log.info("Conectado a PostgreSQL.")
        except SQLAlchemyError as e:
            # No se imprime la URL porque contiene la contraseña.
            log.error("No se pudo conectar a PostgreSQL (%s). El chatbot seguirá "
                      "funcionando sin registrar consultas.", type(e).__name__)
            self.estado = "error"
            self._engine = None

    @property
    def disponible(self) -> bool:
        return self.Sesion is not None

    def cerrar(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
