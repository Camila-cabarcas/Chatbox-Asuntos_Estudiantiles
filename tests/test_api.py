import pytest

from app.config import RAIZ_PROYECTO, get_settings
from app.rag.fichas import leer_ficha


def test_health_responde_sin_base_de_datos(cliente):
    r = cliente.get("/api/health")
    assert r.status_code == 200
    d = r.json()
    assert d["base_datos"] == "deshabilitada"
    assert d["fragmentos_indexados"] > 0


def test_chat_cumple_el_contrato(cliente):
    r = cliente.post("/api/chat", json={"pregunta": "¿Cuándo se reúne el comité?"})
    assert r.status_code == 200
    d = r.json()
    assert set(d) == {"respuesta", "fuentes", "fuera_de_alcance", "id_consulta"}
    assert d["fuera_de_alcance"] is False
    assert d["respuesta"].strip()
    # La fuente se identifica por el título de la ficha: su URL coincide con
    # la del canal oficial, que también se usa en respuestas fuera de alcance.
    comite = leer_ficha(RAIZ_PROYECTO / "fichas" / "comite-sesiones-contacto.md")
    assert comite is not None
    assert {"titulo": comite.titulo, "url": comite.url} in d["fuentes"]
    assert d["id_consulta"] is None  # BD deshabilitada: no falla, solo no registra


FICHAS_DE_PRUEBA = {
    "tramite-uno.md": """---
id: tramite-uno
titulo: Trámite de prueba uno
fuentes:
  - url: https://www.udea.edu.co/prueba-uno
preguntas_ejemplo:
  - ¿Dónde radico la solicitud del trámite uno?
---

## Trámite de prueba uno: ¿qué es?
Solicitud ficticia que se radica en SSOFI ante el comité.
""",
    "tramite-dos.md": """---
id: tramite-dos
titulo: Trámite de prueba dos
fuentes:
  - url: https://www.udea.edu.co/prueba-dos
---

## Trámite de prueba dos: requisitos
Adjuntar la carta firmada en PDF antes del viernes.
""",
}


@pytest.fixture
def fichas_de_prueba(tmp_path, monkeypatch):
    """Carpeta temporal con dos fichas ficticias: la prueba no depende de
    cómo estén redactadas las fichas reales."""
    carpeta = tmp_path / "fichas"
    carpeta.mkdir()
    for nombre, texto in FICHAS_DE_PRUEBA.items():
        (carpeta / nombre).write_text(texto, encoding="utf-8")
    monkeypatch.setenv("FICHAS_PATH", str(carpeta))
    return carpeta


# fichas_de_prueba va antes que cliente: así FICHAS_PATH ya está definido
# cuando se crea la aplicación.
def test_pregunta_fuera_de_alcance(fichas_de_prueba, cliente):
    # El índice se armó con las fichas de prueba, no con las reales.
    assert cliente.get("/api/health").json()["fragmentos_indexados"] < 10

    r = cliente.post("/api/chat", json={"pregunta": "receta de arepas con queso"})
    assert r.status_code == 200
    d = r.json()
    assert d["fuera_de_alcance"] is True
    canal = get_settings().canal_oficial_url
    assert d["fuentes"] == [{"titulo": "Comité de Asuntos Estudiantiles - Facultad de Ingeniería", "url": canal}]


def test_pregunta_vacia_es_rechazada(cliente):
    assert cliente.post("/api/chat", json={"pregunta": ""}).status_code == 422
