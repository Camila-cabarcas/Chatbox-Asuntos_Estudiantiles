from app.config import RAIZ_PROYECTO
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
    assert {"titulo": comite.titulo, "url": comite.url} in d["fuentes"]
    assert d["id_consulta"] is None  # BD deshabilitada: no falla, solo no registra


def test_pregunta_fuera_de_alcance(cliente):
    r = cliente.post("/api/chat", json={"pregunta": "receta de arepas con queso"})
    assert r.status_code == 200
    assert r.json()["fuera_de_alcance"] is True


def test_pregunta_vacia_es_rechazada(cliente):
    assert cliente.post("/api/chat", json={"pregunta": ""}).status_code == 422
