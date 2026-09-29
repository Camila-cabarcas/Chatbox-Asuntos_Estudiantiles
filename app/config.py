"""
Configuración central del proyecto (el equivalente en Python al
`application.properties` de Java).

Todos los valores se leen de variables de entorno o del archivo `.env`.
NUNCA se escriben credenciales en el código: si falta una variable, se usa
el valor por defecto de abajo, que siempre es seguro para desarrollo local.

Uso en cualquier parte del código:
    from app.config import get_settings
    settings = get_settings()
    settings.rag_top_k
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ_PROYECTO / ".env",
        env_file_encoding="utf-8",
        extra="ignore",          # variables desconocidas en .env no rompen nada
        case_sensitive=False,
    )

    # --- Aplicación ---------------------------------------------------------
    app_name: str = "Chatbot Asuntos Estudiantiles - Ingeniería UdeA"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    # Orígenes permitidos para CORS, separados por coma.
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    # --- Base de datos (PostgreSQL) ----------------------------------------
    # Si db_enabled=false el chatbot funciona igual, solo que no registra
    # las consultas. Útil para quien trabaja en la interfaz o en el RAG.
    db_enabled: bool = True
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://chatbot:chatbot_local@localhost:5432/chatbot_uae"
    )

    # --- Modelo de lenguaje (consumido por API) -----------------------------
    # mock: respuestas de prueba sin llamar a ninguna API (no requiere clave).
    # openai_compatible: cualquier proveedor que exponga /chat/completions.
    llm_provider: Literal["mock", "openai_compatible"] = "mock"
    llm_base_url: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    llm_temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    llm_timeout_seconds: float = Field(default=30.0, gt=0)
    llm_max_tokens: int = Field(default=600, gt=0)

    # --- Embeddings ---------------------------------------------------------
    # local: modelo multilingüe preentrenado (sentence-transformers).
    # mock: vectores simples por palabras, sin descargar modelos (pruebas).
    embeddings_provider: Literal["local", "mock"] = "local"
    embeddings_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # --- Índice vectorial y base de conocimiento ---------------------------
    chroma_path: Path = RAIZ_PROYECTO / "data" / "chroma"
    chroma_collection: str = "fichas_uae"
    fichas_path: Path = RAIZ_PROYECTO / "fichas"
    # Reconstruye el índice al arrancar. Necesario en Render (disco efímero).
    index_on_startup: bool = True

    # --- Parámetros del RAG -------------------------------------------------
    rag_top_k: int = Field(default=4, ge=1, le=10)
    # Distancia coseno máxima (0 = idéntico, 2 = opuesto). Si ningún
    # fragmento está por debajo, la pregunta se trata como fuera de alcance.
    rag_max_distance: float = Field(default=0.65, gt=0, le=2)

    # --- Canal oficial para remisiones --------------------------------------
    canal_oficial_url: str = (
        "https://www.udea.edu.co/wps/portal/udea/web/inicio/unidades-academicas/"
        "ingenieria/acerca-facultad/comites/comite-asuntos-estudiantiles"
    )

    # ------------------------------------------------------------------------
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _validar_llm(self) -> "Settings":
        """Si se elige un proveedor real, exige sus datos con un mensaje
        claro en vez de fallar después en medio de una pregunta."""
        if self.llm_provider == "openai_compatible":
            faltan = [
                nombre for nombre, valor in {
                    "LLM_BASE_URL": self.llm_base_url,
                    "LLM_API_KEY": self.llm_api_key.get_secret_value(),
                    "LLM_MODEL": self.llm_model,
                }.items() if not valor
            ]
            if faltan:
                raise ValueError(
                    "LLM_PROVIDER=openai_compatible requiere definir en .env: "
                    + ", ".join(faltan)
                    + ". Para trabajar sin clave use LLM_PROVIDER=mock."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
