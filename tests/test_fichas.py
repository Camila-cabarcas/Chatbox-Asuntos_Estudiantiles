from app.config import RAIZ_PROYECTO
from app.rag.fichas import cargar_fragmentos


def test_fichas_reales_son_validas():
    """Falla si alguien sube una ficha mal escrita a fichas/."""
    fragmentos = cargar_fragmentos(RAIZ_PROYECTO / "fichas")
    assert fragmentos, "No se cargó ninguna ficha"
    assert not any(f.ficha_id == "nombre-del-tramite" for f in fragmentos), \
        "La plantilla no debe indexarse"


def test_ficha_invalida_se_omite_sin_romper(tmp_path):
    (tmp_path / "mala.md").write_text("sin encabezado", encoding="utf-8")
    (tmp_path / "incompleta.md").write_text("---\nid: x\n---\n## A\ntexto", encoding="utf-8")
    (tmp_path / "buena.md").write_text(
        "---\nid: b\ntitulo: B\nfuentes:\n  - url: https://x\n---\n## B: qué es\nAlgo.",
        encoding="utf-8")
    fr = cargar_fragmentos(tmp_path)
    assert [f.ficha_id for f in fr] == ["b"]
    assert fr[0].texto.startswith("B\n")
