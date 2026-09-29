import pytest
from pydantic import ValidationError

from app.config import Settings


def test_proveedor_real_sin_clave_da_error_claro(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    for v in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(v, raising=False)
    with pytest.raises(ValidationError, match="LLM_API_KEY"):
        Settings(_env_file=None)


def test_la_clave_no_se_imprime(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "clave-super-secreta")
    s = Settings(_env_file=None)
    assert "clave-super-secreta" not in repr(s)
