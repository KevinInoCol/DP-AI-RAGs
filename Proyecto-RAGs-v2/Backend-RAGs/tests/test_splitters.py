"""
Tests del paquete splitters/ (catálogos LlamaIndex y LangChain).
Solo prueba las técnicas sin API key: no llama a ningún servicio externo.
Ejecutar desde Backend-RAGs:  python -m pytest tests -q
"""

import json

import pytest

from componentes.splitters import FRAMEWORKS, list_frameworks, list_splitters, split_text
from componentes.splitters import langchain as lc_catalog
from componentes.splitters import llamaindex as li_catalog

TEXTO = (
    "La ingesta convierte PDFs en chunks. Primero se valida el texto nativo. "
    "Si no hay texto, se aplica OCR.\n\n"
    "Después se normaliza y se quita el boilerplate. Luego viene el chunking, "
    "que decide el tamaño de cada fragmento.\n\n"
    "Por último se calculan los embeddings y se guardan en Qdrant."
) * 4

MARKDOWN = "# Manual\nIntro.\n## Trámites\nCómo pedir un certificado.\n### Requisitos\nCédula."
HTML = "<h1>Manual</h1><p>Intro.</p><h2>Trámites</h2><p>Cómo pedir un certificado.</p>"


# --------------------------------------------------------------------------- #
# Organización del catálogo
# --------------------------------------------------------------------------- #
def test_los_catalogos_no_comparten_claves():
    assert not set(li_catalog.SPLITTERS) & set(lc_catalog.SPLITTERS)


def test_las_claves_de_langchain_llevan_prefijo():
    assert all(k.startswith("lc_") for k in lc_catalog.SPLITTERS)
    assert not any(k.startswith("lc_") for k in li_catalog.SPLITTERS)


def test_cada_tecnica_trae_su_framework_en_orden():
    items = list_splitters()
    assert [f["key"] for f in list_frameworks()] == list(FRAMEWORKS)
    # Primero todas las de LlamaIndex y después las de LangChain, sin mezclar.
    frameworks = [it["framework"] for it in items]
    assert frameworks == sorted(frameworks, key=list(FRAMEWORKS).index)
    assert {it["framework"] for it in list_splitters("langchain")} == {"langchain"}


def test_splitter_desconocido():
    with pytest.raises(KeyError):
        split_text("no_existe", "hola")


# --------------------------------------------------------------------------- #
# Técnicas sin API key
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "key",
    [k for k, cfg in lc_catalog.SPLITTERS.items() if cfg["group"] == "no_api" and cfg["output"] == "text" and k != "lc_nltk"],
)
def test_langchain_texto_genera_chunks(key):
    params = {"chunk_size": 120, "chunk_overlap": 20}
    chunks = split_text(key, TEXTO, params)
    assert len(chunks) > 1
    assert [c["index"] for c in chunks] == list(range(len(chunks)))
    assert all(c["token_count"] > 0 and c["char_count"] == len(c["text"]) for c in chunks)


def test_recursive_respeta_el_tamano_en_caracteres():
    chunks = split_text("lc_recursive", TEXTO, {"chunk_size": 150, "chunk_overlap": 0})
    assert max(c["char_count"] for c in chunks) <= 150


def test_recursive_en_tokens():
    chunks = split_text("lc_recursive", TEXTO, {"length_unit": "tokens", "chunk_size": 40, "chunk_overlap": 0})
    assert max(c["token_count"] for c in chunks) <= 40


def test_markdown_header_guarda_los_encabezados_en_metadata():
    chunks = split_text("lc_markdown_header", MARKDOWN, {"max_level": "3"})
    assert chunks[-1]["metadata"] == {"H1": "Manual", "H2": "Trámites", "H3": "Requisitos"}


def test_markdown_header_respeta_el_nivel_maximo():
    chunks = split_text("lc_markdown_header", MARKDOWN, {"max_level": "1"})
    assert len(chunks) == 1 and chunks[0]["metadata"] == {"H1": "Manual"}


def test_html_header_guarda_los_encabezados_en_metadata():
    chunks = split_text("lc_html_header", HTML, {"max_level": "2"})
    assert chunks[-1]["metadata"] == {"H1": "Manual", "H2": "Trámites"}


def test_json_devuelve_chunks_json_validos():
    data = {f"tramite_{i}": {"nombre": f"Trámite {i}", "requisitos": ["cédula", "formulario"]} for i in range(20)}
    chunks = split_text("lc_json", json.dumps(data), {"max_chunk_size": 200})
    assert len(chunks) > 1
    for c in chunks:
        json.loads(c["text"])
    assert "Trámite" in chunks[0]["text"]  # sin escapar los acentos


def test_json_invalido_da_error_claro():
    with pytest.raises(RuntimeError, match="JSON válido"):
        split_text("lc_json", "esto no es json", {})


def test_llamaindex_sigue_funcionando():
    chunks = split_text("sentence", TEXTO, {"chunk_size": 64, "chunk_overlap": 0})
    assert len(chunks) > 1 and chunks[0]["metadata"] is None
