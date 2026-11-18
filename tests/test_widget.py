"""
Pruebas del widget TiToAI (frontend/widget/). Verifican que el servidor lo
entrega, que la página de demostración lo incluye y algunas reglas de
seguridad y privacidad del código del widget.
"""

import re
from html.parser import HTMLParser

from app.config import RAIZ_PROYECTO

WIDGET = RAIZ_PROYECTO / "frontend" / "widget" / "titoai-widget.js"
RUTA_WIDGET = "/widget/titoai-widget.js"


class _Scripts(HTMLParser):
    """Recoge los atributos de cada <script> de una página."""

    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.scripts.append(dict(attrs))


def test_servidor_entrega_el_widget_y_su_avatar(cliente):
    r = cliente.get(RUTA_WIDGET)
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert "attachShadow" in r.text

    avatar = cliente.get("/widget/assets/titoai.png")
    assert avatar.status_code == 200
    assert avatar.headers["content-type"] == "image/png"


def test_index_incluye_el_widget_y_se_conserva_la_prueba_de_api(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    lector = _Scripts()
    lector.feed(r.text)
    widgets = [s for s in lector.scripts if s.get("src") == RUTA_WIDGET]
    assert len(widgets) == 1
    assert "defer" in widgets[0]

    assert cliente.get("/prueba-api.html").status_code == 200


def test_widget_solo_usa_innerhtml_con_iconos_fijos():
    codigo = WIDGET.read_text(encoding="utf-8")
    asignaciones = re.findall(r"innerHTML\s*=\s*([^;]+);", codigo)
    assert asignaciones == ['SVG_INICIO + ICONOS[nombre] + "</svg>"']
    for prohibido in ("outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert prohibido not in codigo


def test_widget_abre_todos_los_enlaces_de_forma_segura():
    codigo = WIDGET.read_text(encoding="utf-8")
    nuevas_pestanas = codigo.count('target: "_blank"')
    assert nuevas_pestanas >= 2  # tarjetas de fuente y enlaces dentro del texto
    assert codigo.count('rel: "noopener noreferrer"') == nuevas_pestanas
    # Todo href pasa antes por urlSegura (solo http y https).
    assert re.findall(r"href: (\w+)", codigo) == ["href", "href"]
    assert codigo.count("const href = urlSegura(") == 2


def test_widget_no_guarda_la_conversacion_ni_carga_recursos_externos():
    codigo = WIDGET.read_text(encoding="utf-8")
    # En localStorage solo se guarda la preferencia de minimizado.
    assert re.findall(r"localStorage\.setItem\(([^,]+),", codigo) == ["CLAVE_MINIMIZADO"]
    assert "sessionStorage" not in codigo
    assert "document.cookie" not in codigo
    # Las únicas URL absolutas son el espacio de nombres SVG y el canal oficial.
    urls = set(re.findall(r"https?://[^\s\"'<>]+", codigo))
    assert urls <= {"http://www.w3.org/2000/svg", "https://servidor",
                    "https://www.udea.edu.co/wps/portal/udea/web/inicio/unidades-academicas/"}
