"""
Conexión a PostgreSQL con SQLAlchemy.

Si la base de datos no está disponible (Docker apagado, credenciales mal
escritas, Neon suspendido), el chatbot NO se cae: sigue respondiendo y solo
deja de registrar consultas. El estado se ve en GET /api/health.

Reconexión: si la base no estaba disponible al arrancar, o se cae después,
se vuelve a intentar como máximo una vez cada REINTENTO_S segundos:
  - desde /api/chat, en un hilo aparte, para no demorar la respuesta;
  - desde /api/health, en el mismo hilo, para que el estado sea el real.
"""

import logging
import threading
import time
from collections.abc import Callable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db.modelos import Base

log = logging.getLogger(__name__)

# Neon suspende la base tras unos minutos sin uso; despertarla toma varios
# segundos (se midieron 5.4 s), así que 5 s no alcanzaban.
CONNECT_TIMEOUT_S = 15
REINTENTO_S = 60


def es_error_de_conexion(e: SQLAlchemyError) -> bool:
    """Errores que indican que la base no está disponible (no, por ejemplo,
    una restricción violada)."""
    return (isinstance(e, (OperationalError, InterfaceError))
            or bool(getattr(e, "connection_invalidated", False)))


class BaseDeDatos:
    def __init__(self, settings: Settings, reloj: Callable[[], float] = time.monotonic,
                 intervalo: float | None = None):
        self.estado = "deshabilitada"
        self._engine: Engine | None = None
        self.Sesion: sessionmaker | None = None
        self._url: str | None = None
        self._reloj = reloj
        self._intervalo = REINTENTO_S if intervalo is None else intervalo
        self._ultimo_intento: float | None = None
        self._lock = threading.Lock()
        self._hilo: threading.Thread | None = None
        if not settings.db_enabled:
            log.info("Base de datos deshabilitada (DB_ENABLED=false).")
            return
        self._url = settings.database_url.get_secret_value()
        self._conectar()

    @property
    def disponible(self) -> bool:
        return self.Sesion is not None

    def sesion(self) -> sessionmaker | None:
        """Fábrica de sesiones, o None si la base no está disponible. Si toca
        reintentar, lanza la reconexión en segundo plano y devuelve None: la
        consulta actual no se registra, pero la respuesta no se demora."""
        if self.Sesion is None and self._toca_reintentar():
            self._ultimo_intento = self._reloj()
            self._hilo = threading.Thread(target=self._conectar, daemon=True,
                                          name="reconexion-bd")
            self._hilo.start()
        return self.Sesion

    def verificar(self) -> str:
        """Estado real de la base para /api/health: comprueba la conexión (o
        reintenta) como máximo una vez por intervalo; entre comprobaciones
        devuelve el último estado conocido."""
        if self._url is None or not self._toca_reintentar():
            return self.estado
        engine = self._engine
        if engine is None:
            self._conectar()
            return self.estado
        self._ultimo_intento = self._reloj()
        try:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            self.estado = "ok"
        except SQLAlchemyError as e:
            self.registrar_fallo(e)
        return self.estado

    def registrar_fallo(self, e: SQLAlchemyError) -> None:
        """Si el error es de conexión, marca la base como caída para que se
        reintente más tarde."""
        if not es_error_de_conexion(e):
            return
        log.error("Se perdió la conexión con PostgreSQL (%s). Se reintentará en "
                  "%.0f s.", type(e).__name__, self._intervalo)
        self.estado = "error"
        self.Sesion = None
        self._ultimo_intento = self._reloj()
        engine, self._engine = self._engine, None
        if engine is not None:
            engine.dispose()

    def cerrar(self) -> None:
        if self._hilo is not None:
            self._hilo.join(timeout=CONNECT_TIMEOUT_S + 5)
        if self._engine is not None:
            self._engine.dispose()

    def _toca_reintentar(self) -> bool:
        return (self._url is not None
                and (self._ultimo_intento is None
                     or self._reloj() - self._ultimo_intento >= self._intervalo))

    def _conectar(self) -> None:
        url = self._url
        # Si otro hilo ya está intentando conectar, no se lanza un segundo intento.
        if url is None or not self._lock.acquire(blocking=False):
            return
        engine: Engine | None = None
        try:
            self._ultimo_intento = self._reloj()
            engine = create_engine(
                url,
                pool_pre_ping=True,        # detecta conexiones caídas
                pool_size=5, max_overflow=5,
                connect_args={"connect_timeout": CONNECT_TIMEOUT_S},
            )
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            # Crea las tablas si no existen. Para un prototipo es suficiente;
            # en un sistema mayor se usarían migraciones (Alembic).
            Base.metadata.create_all(engine)
            self._engine = engine
            self.Sesion = sessionmaker(bind=engine, expire_on_commit=False)
            self.estado = "ok"
            log.info("Conectado a PostgreSQL.")
        except SQLAlchemyError as e:
            # No se imprime la URL porque contiene la contraseña.
            log.error("No se pudo conectar a PostgreSQL (%s). El chatbot seguirá "
                      "funcionando sin registrar consultas; se reintentará en %.0f s.",
                      type(e).__name__, self._intervalo)
            self.estado = "error"
            if engine is not None:
                engine.dispose()
        finally:
            self._lock.release()
