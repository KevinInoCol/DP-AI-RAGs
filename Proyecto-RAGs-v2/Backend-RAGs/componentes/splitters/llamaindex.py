"""
Catálogo de Text Splitters / Node Parsers de LlamaIndex.

Las técnicas de LangChain viven aparte, en `splitters/langchain.py`; el paquete
`splitters` une ambos catálogos.

Cada técnica se describe con:
  - key           : identificador único (usado por el frontend)
  - name          : nombre legible
  - group         : "no_api" (funciona sin conexión) | "api" (requiere una API key
                    de embeddings: GOOGLE_API_KEY u OPENAI_API_KEY)
  - description   : explicación corta
  - params        : parámetros configurables desde la UI (con valores por defecto)
  - factory(params, embed_model) -> NodeParser de LlamaIndex

Las claves son las originales (`sentence`, `token`, ...) para no romper
llamadas existentes a `/split`. Las de LangChain llevan el prefijo `lc_`.

Para dividir un texto se convierte en un Document y se llama a
`node_parser.get_nodes_from_documents([doc])`.
"""

from __future__ import annotations

from typing import Any

from llama_index.core import Document
from llama_index.core.node_parser import (
    CodeSplitter,
    SemanticSplitterNodeParser,
    SentenceSplitter,
    SentenceWindowNodeParser,
    TokenTextSplitter,
)

from .common import FREE_PRICING, SEMANTIC_MODELS, SEMANTIC_PRICING, make_chunk

# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #


def _get_code_parser(language: str):
    """Construye un parser tree-sitter para CodeSplitter.

    La versión de CodeSplitter de LlamaIndex intenta importar el paquete antiguo
    `tree_sitter_languages` (que no compila en Python 3.14). Aquí construimos el
    parser con `tree-sitter-language-pack` y lo pasamos directamente.
    """
    try:
        from tree_sitter_language_pack import get_parser

        return get_parser(language)
    except ImportError as exc:
        raise RuntimeError(
            "Falta 'tree-sitter-language-pack'. Instálalo con: "
            "pip install tree-sitter-language-pack"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Lenguaje no soportado por CodeSplitter: {language} ({exc})") from exc


def _get_embed_model():
    """Modelo de embeddings para los splitters SEMÁNTICOS.

    Reutiliza la resolución del catálogo de embeddings (componentes/embeddings): usa Google
    o OpenAI según qué API key haya en el entorno, con el MISMO modelo y dimensión
    que la etapa de indexación. Si no hay ninguna clave, lanza RuntimeError con el
    mensaje accionable que arma `resolve_embedder`.
    """
    from componentes.embeddings import llama_embed_model

    return llama_embed_model()


# --------------------------------------------------------------------------- #
# Definición de cada splitter
# --------------------------------------------------------------------------- #
# Cada entrada del catálogo. `params` describe los controles de la UI:
#   {name, label, type: "int"|"float"|"select", default, min, max, step, options}

SPLITTERS: dict[str, dict[str, Any]] = {
    # ---------------------- SIN API KEY --------------------------------- #
    "sentence": {
        "name": "SentenceSplitter",
        "provider": "LlamaIndex",
        "pricing": FREE_PRICING,
        "group": "no_api",
        "description": (
            "Divide por tamaño intentando NO romper oraciones. Es el splitter "
            "por defecto y el más usado en RAG."
        ),
        "params": [
            {"name": "chunk_size", "label": "Tamaño de chunk (tokens)", "type": "int", "default": 256, "min": 32, "max": 2048, "step": 32},
            {"name": "chunk_overlap", "label": "Solapamiento (tokens)", "type": "int", "default": 20, "min": 0, "max": 512, "step": 8},
        ],
        "factory": lambda p, _: SentenceSplitter(
            chunk_size=int(p.get("chunk_size", 256)),
            chunk_overlap=int(p.get("chunk_overlap", 20)),
        ),
    },
    "token": {
        "name": "TokenTextSplitter",
        "provider": "LlamaIndex",
        "pricing": FREE_PRICING,
        "group": "no_api",
        "description": (
            "Divide por un número fijo de tokens sin preocuparse por las "
            "fronteras de oración. Rápido y predecible."
        ),
        "params": [
            {"name": "chunk_size", "label": "Tamaño de chunk (tokens)", "type": "int", "default": 256, "min": 32, "max": 2048, "step": 32},
            {"name": "chunk_overlap", "label": "Solapamiento (tokens)", "type": "int", "default": 20, "min": 0, "max": 512, "step": 8},
        ],
        "factory": lambda p, _: TokenTextSplitter(
            chunk_size=int(p.get("chunk_size", 256)),
            chunk_overlap=int(p.get("chunk_overlap", 20)),
        ),
    },
    "sentence_window": {
        "name": "SentenceWindowNodeParser",
        "provider": "LlamaIndex",
        "pricing": FREE_PRICING,
        "group": "no_api",
        "description": (
            "Crea un nodo por cada oración y guarda una 'ventana' de N oraciones "
            "alrededor como contexto (en metadata: window)."
        ),
        "params": [
            {"name": "window_size", "label": "Tamaño de ventana (oraciones)", "type": "int", "default": 3, "min": 1, "max": 10, "step": 1},
        ],
        "factory": lambda p, _: SentenceWindowNodeParser.from_defaults(
            window_size=int(p.get("window_size", 3)),
            window_metadata_key="window",
            original_text_metadata_key="original_sentence",
        ),
    },
    "code": {
        "name": "CodeSplitter",
        "provider": "LlamaIndex (tree-sitter)",
        "pricing": FREE_PRICING,
        "group": "no_api",
        "description": (
            "Divide código fuente respetando su sintaxis (usa el AST del "
            "lenguaje). Ideal para indexar repositorios."
        ),
        "params": [
            {"name": "language", "label": "Lenguaje", "type": "select", "default": "python",
             "options": ["python", "javascript", "typescript", "java", "go", "cpp", "html"]},
            {"name": "chunk_lines", "label": "Líneas por chunk", "type": "int", "default": 40, "min": 5, "max": 200, "step": 5},
            {"name": "chunk_lines_overlap", "label": "Solapamiento (líneas)", "type": "int", "default": 15, "min": 0, "max": 100, "step": 5},
            {"name": "max_chars", "label": "Máx. caracteres", "type": "int", "default": 1500, "min": 200, "max": 8000, "step": 100},
        ],
        "factory": lambda p, _: CodeSplitter(
            language=str(p.get("language", "python")),
            chunk_lines=int(p.get("chunk_lines", 40)),
            chunk_lines_overlap=int(p.get("chunk_lines_overlap", 15)),
            max_chars=int(p.get("max_chars", 1500)),
            parser=_get_code_parser(str(p.get("language", "python"))),
        ),
    },
    # ------------- CON API KEY (embeddings: Google u OpenAI) ------------ #
    "semantic": {
        "name": "SemanticSplitterNodeParser",
        "provider": "LlamaIndex + embeddings (Google u OpenAI)",
        "pricing": SEMANTIC_PRICING,
        "group": "api",
        "description": (
            f"Divide por SIMILITUD SEMÁNTICA: usa embeddings ({SEMANTIC_MODELS}) "
            "para detectar dónde cambia el tema y corta ahí. Los chunks son de tamaño "
            "adaptativo. Requiere una API key de embeddings (GOOGLE_API_KEY u "
            "OPENAI_API_KEY): usa el mismo modelo que la etapa de indexación."
        ),
        "params": [
            {"name": "buffer_size", "label": "Buffer (oraciones)", "type": "int", "default": 1, "min": 1, "max": 5, "step": 1},
            {"name": "breakpoint_percentile_threshold", "label": "Umbral de corte (percentil)", "type": "int", "default": 95, "min": 50, "max": 99, "step": 1},
        ],
        "factory": lambda p, embed: SemanticSplitterNodeParser(
            buffer_size=int(p.get("buffer_size", 1)),
            breakpoint_percentile_threshold=int(p.get("breakpoint_percentile_threshold", 95)),
            embed_model=embed,
        ),
    },
}


def split(cfg: dict[str, Any], text: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Aplica una entrada del catálogo: texto -> Document -> nodes -> chunks."""
    embed_model = _get_embed_model() if cfg["group"] == "api" else None
    parser = cfg["factory"](params, embed_model)

    nodes = parser.get_nodes_from_documents([Document(text=text)])
    # Para SentenceWindow mostramos también la ventana de contexto.
    return [
        make_chunk(i, node.get_content(), window=(node.metadata or {}).get("window"))
        for i, node in enumerate(nodes)
    ]
