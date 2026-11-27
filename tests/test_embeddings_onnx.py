"""
Proveedor de embeddings ONNX (EMBEDDINGS_PROVIDER=onnx).

Las primeras pruebas reemplazan ONNX Runtime y SentencePiece por versiones
falsas: corren sin internet y sin el modelo. Las del final usan el modelo
real y se saltan si no está descargado (python -m scripts.descargar_modelo).
"""

import math

import numpy as np
import onnxruntime
import pytest
import sentencepiece

from app.config import Settings
from app.rag.embeddings import EmbeddingsMock, EmbeddingsOnnx, crear_embeddings
from app.rag.indice import IndiceVectorial

DIM = 4


class SentencePieceFalso:
    """Cada carácter es una pieza: su id es el código del carácter, salvo
    '?', que SentencePiece no conoce (id 0 = <unk>)."""

    def __init__(self, model_file):
        self.archivo = model_file

    def encode(self, texto):
        return [0 if c == "?" else ord(c) for c in texto]


class SesionFalsa:
    """Devuelve, para cada token, un vector que depende solo de su id (los
    de relleno valen 1000, para notar si se colaran en el promedio)."""

    instancias: list["SesionFalsa"] = []

    def __init__(self, ruta, opciones, providers):
        self.ruta, self.opciones, self.providers = ruta, opciones, providers
        self.lotes: list[dict] = []
        SesionFalsa.instancias.append(self)

    def get_inputs(self):
        class Entrada:
            def __init__(self, nombre):
                self.name = nombre
        return [Entrada("input_ids"), Entrada("attention_mask"), Entrada("token_type_ids")]

    def run(self, salidas, entradas):
        self.lotes.append(entradas)
        ids = entradas["input_ids"].astype(np.float32)
        vectores = np.stack([ids, np.ones_like(ids), ids % 7, np.full_like(ids, 2.0)], axis=-1)
        vectores[entradas["input_ids"] == EmbeddingsOnnx.PAD] = 1000.0
        return [vectores]


@pytest.fixture
def onnx(tmp_path, monkeypatch):
    SesionFalsa.instancias = []
    monkeypatch.setattr(onnxruntime, "InferenceSession", SesionFalsa)
    monkeypatch.setattr(sentencepiece, "SentencePieceProcessor", SentencePieceFalso)
    modelo, tokenizador = tmp_path / "model.onnx", tmp_path / "sp.model"
    modelo.write_bytes(b"")
    tokenizador.write_bytes(b"")
    return EmbeddingsOnnx(modelo, tokenizador, "modelo-prueba", max_tokens=6)


def test_sesion_con_un_hilo_sin_arena_y_en_cpu(onnx):
    sesion = SesionFalsa.instancias[0]
    assert sesion.opciones.intra_op_num_threads == 1
    assert sesion.opciones.inter_op_num_threads == 1
    assert sesion.opciones.enable_cpu_mem_arena is False
    assert sesion.providers == ["CPUExecutionProvider"]


def test_ids_con_especiales_y_desplazamiento_de_fairseq(onnx):
    # <s>=0, </s>=2; los ids de SentencePiece se corren en 1 y su <unk> (0) pasa a 3.
    assert onnx._ids("ab?") == [0, ord("a") + 1, ord("b") + 1, 3, 2]
    assert onnx.contar_tokens("ab?") == 5
    assert onnx.contar_tokens("") == 2


def test_contar_tokens_no_recorta(onnx):
    # El troceado necesita el largo real para decidir si divide el texto.
    assert onnx.contar_tokens("x" * 20) == 22


def test_recorte_conserva_el_inicio_y_el_cierre(onnx):
    ids = onnx._ids("abcdefgh")
    assert onnx._recortar(ids) == ids[:5] + [EmbeddingsOnnx.EOS]
    assert len(onnx._recortar(ids)) == onnx.max_tokens
    assert onnx._recortar(onnx._ids("ab")) == onnx._ids("ab")


def test_lotes_de_ocho(onnx):
    vectores = onnx.embed([f"t{i}" for i in range(19)])
    lotes = SesionFalsa.instancias[0].lotes
    assert len(vectores) == 19
    assert [len(lote["input_ids"]) for lote in lotes] == [8, 8, 3]


def test_relleno_fuera_del_promedio_y_vectores_normalizados(onnx):
    # "a" sola y junto a un texto más largo (que obliga a rellenar "a")
    # deben dar exactamente el mismo vector.
    sola = onnx.embed(["a"])[0]
    con_relleno = onnx.embed(["a", "abcdef"])[0]
    assert sola == pytest.approx(con_relleno)
    lote = SesionFalsa.instancias[0].lotes[-1]
    assert lote["attention_mask"].tolist()[0] == [1, 1, 1, 0, 0, 0]
    assert lote["input_ids"].tolist()[0][3:] == [EmbeddingsOnnx.PAD] * 3
    assert lote["token_type_ids"].tolist() == np.zeros((2, 6), dtype=int).tolist()
    for v in onnx.embed(["a", "texto largo que se recorta"]):
        assert len(v) == DIM
        assert math.sqrt(sum(x * x for x in v)) == pytest.approx(1.0)


def test_nombre_identifica_modelo_y_variante(onnx):
    assert onnx.nombre == "onnx:modelo-prueba/model.onnx"
    assert onnx.conteo_exacto is True


def test_sin_archivos_explica_como_descargarlos(tmp_path):
    with pytest.raises(RuntimeError, match="scripts.descargar_modelo"):
        EmbeddingsOnnx(tmp_path / "no.onnx", tmp_path / "no.model", "m")


def test_crear_embeddings_elige_onnx(tmp_path, monkeypatch):
    monkeypatch.setattr(onnxruntime, "InferenceSession", SesionFalsa)
    monkeypatch.setattr(sentencepiece, "SentencePieceProcessor", SentencePieceFalso)
    s = Settings(_env_file=None, embeddings_provider="onnx", embeddings_onnx_dir=tmp_path,  # pyright: ignore[reportCallIssue]
                 embeddings_onnx_archivo="variante.onnx")
    assert s.embeddings_onnx_ruta == tmp_path / "onnx" / "variante.onnx"
    assert s.embeddings_tokenizador_ruta == tmp_path / "sentencepiece.bpe.model"
    s.embeddings_onnx_ruta.parent.mkdir()
    s.embeddings_onnx_ruta.write_bytes(b"")
    s.embeddings_tokenizador_ruta.write_bytes(b"")
    e = crear_embeddings(s)
    assert isinstance(e, EmbeddingsOnnx)
    assert e.max_tokens == 128


# --- Índice construido con otro modelo ---------------------------------------

class OtroMock(EmbeddingsMock):
    def __init__(self):
        super().__init__()
        self.nombre = "otro-modelo"


def test_indice_de_otro_modelo_no_es_vigente(tmp_path):
    s = Settings(_env_file=None, chroma_path=tmp_path / "chroma")  # pyright: ignore[reportCallIssue]
    indice = IndiceVectorial(s, EmbeddingsMock())
    assert not indice.vigente()          # vacío
    indice.reconstruir()
    assert indice.vigente()
    assert IndiceVectorial(s, EmbeddingsMock()).vigente()
    assert not IndiceVectorial(s, OtroMock()).vigente()


def test_arranque_reconstruye_el_indice_de_otro_modelo(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import crear_app

    ruta = tmp_path / "chroma"
    s = Settings(_env_file=None, chroma_path=ruta)  # pyright: ignore[reportCallIssue]
    viejo = IndiceVectorial(s, OtroMock())
    viejo.reconstruir()
    del viejo

    for var, valor in {"APP_ENV": "test", "LLM_PROVIDER": "mock", "EMBEDDINGS_PROVIDER": "mock",
                       "DB_ENABLED": "false", "CHROMA_PATH": str(ruta), "INDEX_ON_STARTUP": "false"}.items():
        monkeypatch.setenv(var, valor)
    get_settings.cache_clear()
    try:
        app = crear_app()
        with TestClient(app):
            assert app.state.indice.vigente()
    finally:
        get_settings.cache_clear()


# --- Con el modelo real (si está descargado) ---------------------------------

_S = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
real = pytest.mark.skipif(
    not (_S.embeddings_onnx_ruta.is_file() and _S.embeddings_tokenizador_ruta.is_file()),
    reason="modelo ONNX no descargado (python -m scripts.descargar_modelo --sin-indice)")


@pytest.fixture(scope="module")
def modelo_real():
    return EmbeddingsOnnx(_S.embeddings_onnx_ruta, _S.embeddings_tokenizador_ruta, _S.embeddings_model)


@real
def test_modelo_real_ordena_por_significado(modelo_real):
    p, parecida, otra = modelo_real.embed([
        "¿Cómo cancelo una materia fuera de plazo?",
        "Quiero cancelar un curso después de la fecha límite",
        "¿Cuál es la capital de Francia?",
    ])
    assert len(p) == 384
    coseno = lambda a, b: sum(x * y for x, y in zip(a, b))  # noqa: E731
    assert coseno(p, parecida) > coseno(p, otra) + 0.2


@real
def test_modelo_real_tokeniza_igual_que_hugging_face(modelo_real):
    transformers = pytest.importorskip("transformers")
    tok = transformers.AutoTokenizer.from_pretrained(_S.embeddings_model)
    textos = ["¿Qué es la homologación de materias?", "Exoneración de prerrequisito: requisitos",
              "  espacios   dobles\ty tabulación\n", "Ññ ÁÉÍÓÚ ü — “comillas” ½"]
    for t in textos:
        assert modelo_real._ids(t) == tok(t)["input_ids"], t
