"""
Reconexión a la base de datos: si no estaba disponible al arrancar (por
ejemplo, Neon suspendido), se reintenta como máximo una vez por intervalo,
el chatbot sigue respondiendo y /api/health muestra el estado real.

Sin PostgreSQL ni red: create_engine se reemplaza por un SQLite en una
carpeta temporal, y un reloj falso controla el paso del tiempo.
"""

import threading

import pytest
import sqlalchemy
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, OperationalError

from app.config import Settings
from app.db import conexion
from app.db.conexion import CONNECT_TIMEOUT_S, BaseDeDatos
from app.db.repositorio import RepositorioConsultas

DATOS = dict(pregunta="¿Cuándo se reúne el comité?", respuesta="Los martes.", fichas_usadas=[],
             fuera_de_alcance=False, error=False, latencia_ms=10, proveedor_llm="mock")


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


class FabricaDeMotores:
    """Hace las veces de create_engine: con `disponible=False` devuelve un
    SQLite cuya carpeta no existe, así que conectar falla con
    OperationalError, como cuando la base no responde."""

    def __init__(self, carpeta):
        self.disponible = False
        self.llamadas: list[dict] = []
        self.hilos: list[str] = []
        self._ok = f"sqlite:///{(carpeta / 'consultas.db').as_posix()}"
        self._caida = f"sqlite:///{(carpeta / 'no_existe' / 'x.db').as_posix()}"

    def __call__(self, url, **kwargs):
        self.llamadas.append(kwargs)
        self.hilos.append(threading.current_thread().name)
        return sqlalchemy.create_engine(self._ok if self.disponible else self._caida)


@pytest.fixture
def fabrica(tmp_path, monkeypatch):
    f = FabricaDeMotores(tmp_path)
    monkeypatch.setattr(conexion, "create_engine", f)
    return f


def ajustes() -> Settings:
    return Settings(_env_file=None, db_enabled=True,  # pyright: ignore[reportCallIssue]
                    database_url="postgresql+psycopg://usuario:clave@base.invalid/db")


def nueva_bd(reloj) -> BaseDeDatos:
    return BaseDeDatos(ajustes(), reloj=reloj, intervalo=60)


def esperar_reconexion(db: BaseDeDatos) -> None:
    if db._hilo is not None:
        db._hilo.join(timeout=10)


def test_connect_timeout_de_15_segundos(fabrica):
    fabrica.disponible = True
    nueva_bd(Reloj())
    assert fabrica.llamadas[0]["connect_args"] == {"connect_timeout": 15}
    assert CONNECT_TIMEOUT_S == 15


def test_sin_base_al_arrancar_el_registro_no_falla(fabrica):
    db = nueva_bd(Reloj())
    assert db.estado == "error"
    assert RepositorioConsultas(db).registrar(**DATOS) is None
    assert RepositorioConsultas(db).valorar(1, True) is False


def test_no_reintenta_antes_del_intervalo(fabrica):
    reloj = Reloj()
    db = nueva_bd(reloj)
    fabrica.disponible = True
    reloj.t += 59
    assert RepositorioConsultas(db).registrar(**DATOS) is None
    assert db.verificar() == "error"
    assert len(fabrica.llamadas) == 1    # solo el intento del arranque


def test_reintenta_en_segundo_plano_desde_el_chat(fabrica):
    reloj = Reloj()
    db = nueva_bd(reloj)
    repo = RepositorioConsultas(db)
    fabrica.disponible = True
    reloj.t += 60

    # La consulta que dispara el reintento no espera la conexión: se hace en
    # otro hilo.
    repo.registrar(**DATOS)
    esperar_reconexion(db)
    assert fabrica.hilos == ["MainThread", "reconexion-bd"]
    assert db.estado == "ok"
    assert isinstance(repo.registrar(**DATOS), int)


def test_un_solo_reintento_por_intervalo(fabrica):
    reloj = Reloj()
    db = nueva_bd(reloj)
    repo = RepositorioConsultas(db)
    reloj.t += 60
    for _ in range(5):              # la base sigue caída
        repo.registrar(**DATOS)
    esperar_reconexion(db)
    assert len(fabrica.llamadas) == 2    # arranque + un reintento


def test_health_refleja_el_estado_real(fabrica):
    reloj = Reloj()
    db = nueva_bd(reloj)
    assert db.verificar() == "error"

    fabrica.disponible = True
    reloj.t += 60
    assert db.verificar() == "ok"          # reintenta en el mismo hilo
    assert isinstance(RepositorioConsultas(db).registrar(**DATOS), int)


def test_caida_en_marcha_se_detecta_y_se_recupera(fabrica, monkeypatch):
    fabrica.disponible = True
    reloj = Reloj()
    db = nueva_bd(reloj)
    repo = RepositorioConsultas(db)
    assert db.estado == "ok"

    def sesion_caida():
        raise OperationalError("INSERT", {}, Exception("se cerró la conexión"))

    monkeypatch.setattr(db, "Sesion", sesion_caida)
    assert repo.registrar(**DATOS) is None
    assert db.estado == "error"
    assert db.verificar() == "error"       # todavía no toca reintentar

    reloj.t += 60
    assert db.verificar() == "ok"
    assert isinstance(repo.registrar(**DATOS), int)


def test_un_error_que_no_es_de_conexion_no_marca_la_base_caida(fabrica):
    fabrica.disponible = True
    db = nueva_bd(Reloj())
    db.registrar_fallo(IntegrityError("INSERT", {}, Exception("restricción violada")))
    assert db.estado == "ok"
    assert db.disponible


def test_base_deshabilitada_no_intenta_conectar(fabrica):
    db = BaseDeDatos(Settings(_env_file=None, db_enabled=False))  # pyright: ignore[reportCallIssue]
    assert db.verificar() == "deshabilitada"
    assert db.sesion() is None
    assert fabrica.llamadas == []


# --- A través de la API -------------------------------------------------------

@pytest.fixture
def cliente_con_bd(tmp_path, monkeypatch, fabrica):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "mock")
    monkeypatch.setenv("DB_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://usuario:clave@base.invalid/db")
    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("RAG_MAX_DISTANCE", "0.65")
    # Sin espera entre reintentos, para no depender del reloj real.
    monkeypatch.setattr(conexion, "REINTENTO_S", 0)

    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import crear_app

    with TestClient(crear_app()) as c:
        yield c
    get_settings.cache_clear()


def test_api_responde_sin_base_y_se_recupera(cliente_con_bd, fabrica):
    assert cliente_con_bd.get("/api/health").json()["base_datos"] == "error"
    r = cliente_con_bd.post("/api/chat", json={"pregunta": "¿Cuándo se reúne el comité?"})
    assert r.status_code == 200
    assert r.json()["respuesta"].strip()
    assert r.json()["id_consulta"] is None

    esperar_reconexion(cliente_con_bd.app.state.db)   # el reintento lanzado por el chat
    fabrica.disponible = True
    assert cliente_con_bd.get("/api/health").json()["base_datos"] == "ok"
    r = cliente_con_bd.post("/api/chat", json={"pregunta": "¿Cuándo se reúne el comité?"})
    assert isinstance(r.json()["id_consulta"], int)
