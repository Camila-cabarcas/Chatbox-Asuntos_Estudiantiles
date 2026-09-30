"""
Cliente del modelo de lenguaje consumido por API.

Proveedores (LLM_PROVIDER en .env):
  - mock: no llama a ninguna API. Devuelve el fragmento más relevante. Sirve
          para desarrollar la interfaz y el backend sin clave ni costos.
  - openai_compatible: cualquier proveedor que implemente el endpoint
          POST {LLM_BASE_URL}/chat/completions (formato de OpenAI). Muchos
          proveedores y servidores locales lo soportan; revisen la
          documentación del que elijan para obtener LLM_BASE_URL y LLM_MODEL.

Si la API falla (sin internet, clave inválida, límite de uso), se lanza
LLMError y el servicio responde con un mensaje amable en vez de caerse.
"""

import logging
from typing import Protocol

import httpx

from app.config import Settings

log = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class LLM(Protocol):
    nombre: str

    def generar(self, sistema: str, usuario: str) -> str: ...


class LLMMock:
    nombre = "mock"

    def generar(self, sistema: str, usuario: str) -> str:
        contexto = usuario.split("CONTEXTO:", 1)[-1].split("PREGUNTA DEL ESTUDIANTE:", 1)[0]
        primer_fragmento = contexto.strip().split("\n\n---\n\n")[0]
        return ("[Respuesta de prueba - LLM_PROVIDER=mock]\n"
                "Según la información oficial:\n" + primer_fragmento)


class LLMOpenAICompatible:
    def __init__(self, settings: Settings):
        self._url = settings.llm_base_url.rstrip("/") + "/chat/completions"
        self._clave = settings.llm_api_key
        self._modelo = settings.llm_model
        self._temperatura = settings.llm_temperature
        self._max_tokens = settings.llm_max_tokens
        self._timeout = settings.llm_timeout_seconds
        self.nombre = f"openai_compatible:{settings.llm_model}"

    def generar(self, sistema: str, usuario: str) -> str:
        cuerpo = {
            "model": self._modelo,
            "temperature": self._temperatura,
            "max_tokens": self._max_tokens,
            "messages": [
                {"role": "system", "content": sistema},
                {"role": "user", "content": usuario},
            ],
        }
        cabeceras = {"Authorization": f"Bearer {self._clave.get_secret_value()}"}
        try:
            r = httpx.post(self._url, json=cuerpo, headers=cabeceras, timeout=self._timeout)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except httpx.HTTPStatusError as e:
            # No se registra el cuerpo de la petición para no filtrar datos.
            log.error("El proveedor LLM respondió %s", e.response.status_code)
            raise LLMError(f"HTTP {e.response.status_code}") from e
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            log.error("Error llamando al proveedor LLM: %s", type(e).__name__)
            raise LLMError(str(type(e).__name__)) from e


def crear_llm(settings: Settings) -> LLM:
    if settings.llm_provider == "openai_compatible":
        return LLMOpenAICompatible(settings)
    return LLMMock()
