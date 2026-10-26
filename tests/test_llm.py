"""
Tratamiento de la respuesta del modelo: frase de "no encontré información",
razonamiento interno (<think>) y respuestas cortadas por LLM_MAX_TOKENS.
Todo con el LLM mock o con httpx simulado: ninguna prueba llama a Groq.
"""

import logging

import httpx
import pytest

from app.config import Settings
from app.rag import prompts
from app.rag.llm import LLMMock, LLMOpenAICompatible, RespuestaLLM, quitar_razonamiento
from app.rag.servicio import es_sin_informacion

CANAL = Settings.model_fields["canal_oficial_url"].default
PREGUNTA = {"pregunta": "¿Cuándo se reúne el comité?"}


def mock_responde(monkeypatch, respuesta: RespuestaLLM):
    monkeypatch.setattr(LLMMock, "generar", lambda self, sistema, usuario: respuesta)


# --- Ajuste 4: el modelo dice que no tiene la información -----------------

def test_frase_sin_informacion_del_modelo_marca_fuera_de_alcance(cliente, monkeypatch):
    mock_responde(monkeypatch, RespuestaLLM(prompts.RESPUESTA_FUERA_DE_ALCANCE.format(canal_oficial=CANAL)))
    d = cliente.post("/api/chat", json=PREGUNTA).json()
    assert d["fuera_de_alcance"] is True
    assert d["fuentes"] == [{"titulo": "Comité de Asuntos Estudiantiles - Facultad de Ingeniería", "url": CANAL}]
    assert d["respuesta"] == prompts.RESPUESTA_FUERA_DE_ALCANCE.format(canal_oficial=CANAL)


@pytest.mark.parametrize("texto", [
    "No encontré información sobre eso en las fuentes oficiales.",
    "  «No encontré información sobre eso.»",
    "**No encontré información sobre eso** en la información oficial.",
])
def test_reconoce_variantes_de_la_frase(texto):
    assert es_sin_informacion(texto)


def test_no_confunde_una_respuesta_normal():
    assert not es_sin_informacion("El comité se reúne todos los martes. No encontré información sobre eso otro.")


def test_el_prompt_incluye_la_frase_exacta_y_el_canal():
    s = prompts.sistema(CANAL)
    assert prompts.RESPUESTA_FUERA_DE_ALCANCE.format(canal_oficial=CANAL) in s
    assert f"incluye siempre su enlace: {CANAL}" in s
    assert "{" not in s  # no quedaron marcadores sin reemplazar


# --- Ajuste 6: razonamiento interno -----------------------------------------

def test_quita_bloque_think_de_la_respuesta(cliente, monkeypatch):
    mock_responde(monkeypatch, RespuestaLLM("<think>El usuario pregunta por...</think>\nSe reúne los martes."))
    d = cliente.post("/api/chat", json=PREGUNTA).json()
    assert d["respuesta"] == "Se reúne los martes."
    assert "think" not in d["respuesta"].lower()


def test_solo_razonamiento_sin_respuesta_devuelve_mensaje_de_error(cliente, monkeypatch):
    mock_responde(monkeypatch, RespuestaLLM("<think>Razonamiento que nunca se cerró porque se acabó", recortada=True))
    d = cliente.post("/api/chat", json=PREGUNTA).json()
    assert d["respuesta"] == prompts.RESPUESTA_ERROR_LLM.format(canal_oficial=CANAL)


@pytest.mark.parametrize("entrada,salida", [
    ("<think>a</think>b", "b"),
    ("<THINK>\nvarias\nlíneas\n</THINK>\n\nRespuesta", "Respuesta"),
    ("Respuesta sin razonamiento", "Respuesta sin razonamiento"),
    ("<think>sin cerrar", ""),
])
def test_quitar_razonamiento(entrada, salida):
    assert quitar_razonamiento(entrada) == salida


# --- Ajuste 3: respuesta cortada por LLM_MAX_TOKENS ------------------------

def test_respuesta_cortada_avisa_y_remite(cliente, monkeypatch, caplog):
    mock_responde(monkeypatch, RespuestaLLM("Teléfono: 2198502. Correo oficial: asuntoses.ing", recortada=True))
    with caplog.at_level(logging.WARNING):
        d = cliente.post("/api/chat", json=PREGUNTA).json()
    assert d["respuesta"].startswith("Teléfono: 2198502. Correo oficial: asuntoses.ing")
    assert d["respuesta"].endswith(prompts.NOTA_RESPUESTA_INCOMPLETA.format(canal_oficial=CANAL))
    assert "LLM_MAX_TOKENS" in caplog.text


def test_respuesta_completa_no_lleva_nota(cliente, monkeypatch):
    mock_responde(monkeypatch, RespuestaLLM("Se reúne los martes."))
    assert cliente.post("/api/chat", json=PREGUNTA).json()["respuesta"] == "Se reúne los martes."


@pytest.mark.parametrize("finish_reason,recortada", [("length", True), ("stop", False)])
def test_cliente_openai_lee_finish_reason(monkeypatch, finish_reason, recortada):
    s = Settings(_env_file=None, llm_provider="openai_compatible",  # pyright: ignore[reportCallIssue]
                 llm_base_url="https://proveedor.invalid/v1", llm_api_key="clave-falsa", llm_model="modelo")

    def post_falso(url, **kwargs):
        cuerpo = {"choices": [{"message": {"role": "assistant", "content": " Hola "},
                               "finish_reason": finish_reason}]}
        return httpx.Response(200, json=cuerpo, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post_falso)
    r = LLMOpenAICompatible(s).generar("sistema", "usuario")
    assert r == RespuestaLLM("Hola", recortada=recortada)
