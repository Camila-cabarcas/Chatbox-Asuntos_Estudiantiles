"""
Configuración de las pruebas: todo corre sin internet, sin claves, sin
Docker y sin descargar modelos, usando los proveedores "mock".
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "mock")
    monkeypatch.setenv("DB_ENABLED", "false")
    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("RAG_MAX_DISTANCE", "0.9")

    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import crear_app

    with TestClient(crear_app()) as c:
        yield c
    get_settings.cache_clear()
