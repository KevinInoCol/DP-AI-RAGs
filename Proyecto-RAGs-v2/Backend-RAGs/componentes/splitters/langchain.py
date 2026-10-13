"""
Catálogo de Text Splitters de LangChain (`langchain-text-splitters`).

Mismo formato de entrada que `splitters/llamaindex.py`, con dos diferencias:
  - las claves llevan el prefijo `lc_` para no chocar con las de LlamaIndex;
  - `factory(params, embeddings)` devuelve un TextSplitter de LangChain. Su
    `split_text` devuelve str, salvo en los de encabezados (Markdown/HTML), que
    devuelven Documents con los encabezados en la metadata.

OJO con las unidades: en LangChain `chunk_size` se mide en CARACTERES salvo en
`TokenTextSplitter` y en el modo "tokens" del recursivo. En LlamaIndex se mide
en tokens.

El SemanticChunker vive en `langchain-experimental`, que LangChain marcó como
"sunset" (sin mantenimiento activo). Se incluye para comparar con el
SemanticSplitterNodeParser de LlamaIndex, pero no conviene llevarlo a producción.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_text_splitters import (
    CharacterTextSplitter,
    HTMLHeaderTextSplitter,
    Language,
    MarkdownHeaderTextSplitter,
    NLTKTextSplitter,
    RecursiveCharacterTextSplitter,
    RecursiveJsonSplitter,
    TokenTextSplitter,
)

from .common import FREE_PRICING, SEMANTIC_MODELS, SEMANTIC_PRICING, make_chunk

# --------------------------------------------------------------------------- #
# Constantes
# --------------------------------------------------------------------------- #
# Separadores del CharacterTextSplitter: etiqueta de la UI -> separador real.
_SEPARATORS = {
    "párrafo (\\n\\n)": "\n\n",
    "línea (\\n)": "\n",
    "oración ('. ')": ". ",
    "espacio (' ')": " ",
}

# Lenguajes de RecursiveCharacterTextSplitter.from_language que se ofrecen.
_CODE_LANGUAGES = [
    Language.PYTHON, Language.JS, Language.TS, Language.JAVA, Language.GO,
    Language.CPP, Language.CSHARP, Language.PHP, Language.RUBY, Language.RUST,
    Language.MARKDOWN, Language.LATEX, Language.HTML,
]

_YES_NO = ["sí", "no"]


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
class _EmbeddingsAdapter(Embeddings):
    """Expone el embedder de LlamaIndex (componentes/embeddings) con la interfaz de LangChain.

    Así el SemanticChunker usa el MISMO modelo y dimensión que la indexación
    (Google u OpenAI según la API key) sin sumar `langchain-google-genai` ni
    `langchain-openai` como dependencias.
    """

    def __init__(self, llama_model: Any) -> None:
        self._model = llama_model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._model.get_text_embedding_batch(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._model.get_query_embedding(text)


def _get_embeddings() -> Embeddings:
    """Embeddings para el SemanticChunker. Si no hay ninguna API key, lanza
    RuntimeError con el mensaje accionable de `resolve_embedder`."""
    from componentes.embeddings import llama_embed_model

    return _EmbeddingsAdapter(llama_embed_model())


def _ensure_nltk_punkt() -> None:
    """NLTKTextSplitter necesita el tokenizador `punkt_tab`. Se descarga la
    primera vez (unos pocos MB) si no está en el equipo."""
    import nltk

    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        if not nltk.download("punkt_tab", quiet=True):
            raise RuntimeError(
                "No se pudo descargar el tokenizador 'punkt_tab' de NLTK. "
                "Ejecuta: python -m nltk.downloader punkt_tab"
            ) from None


def _recursive(p: dict[str, Any]) -> RecursiveCharacterTextSplitter:
    size = int(p.get("chunk_size", 1000))
    overlap = int(p.get("chunk_overlap", 200))
    if p.get("length_unit", "caracteres") == "tokens":
        return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base", chunk_size=size, chunk_overlap=overlap
        )
    return RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)


def _nltk(p: dict[str, Any]) -> NLTKTextSplitter:
    _ensure_nltk_punkt()
    return NLTKTextSplitter(
        separator=" ",  # une las oraciones de un chunk con espacio (por defecto: \n\n)
        language=str(p.get("language", "spanish")),
        chunk_size=int(p.get("chunk_size", 1000)),
        chunk_overlap=int(p.get("chunk_overlap", 200)),
    )


def _markdown_headers(p: dict[str, Any]) -> MarkdownHeaderTextSplitter:
    max_level = int(p.get("max_level", 3))
    return MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#" * n, f"H{n}") for n in range(1, max_level + 1)],
        strip_headers=p.get("strip_headers", "no") == "sí",
    )


def _html_headers(p: dict[str, Any]) -> HTMLHeaderTextSplitter:
    max_level = int(p.get("max_level", 3))
    return HTMLHeaderTextSplitter(
        headers_to_split_on=[(f"h{n}", f"H{n}") for n in range(1, max_level + 1)],
    )


def _semantic(p: dict[str, Any], embeddings: Embeddings):
    from langchain_experimental.text_splitter import SemanticChunker

    amount = float(p.get("breakpoint_threshold_amount", 0))
    return SemanticChunker(
        embeddings,
        buffer_size=int(p.get("buffer_size", 1)),
        breakpoint_threshold_type=str(p.get("breakpoint_threshold_type", "percentile")),
        # 0 = usar el valor por defecto de cada tipo (95 percentil, 3 desv., ...).
        breakpoint_threshold_amount=amount or None,
    )


_SIZE_CHARS = {"name": "chunk_size", "label": "Tamaño de chunk (caracteres)", "type": "int", "default": 1000, "min": 50, "max": 8000, "step": 50}
_OVERLAP_CHARS = {"name": "chunk_overlap", "label": "Solapamiento (caracteres)", "type": "int", "default": 200, "min": 0, "max": 2000, "step": 10}


# --------------------------------------------------------------------------- #
# Definición de cada splitter
# --------------------------------------------------------------------------- #
# `output`: "text" -> split_text devuelve str | "docs" -> devuelve Documents con
# metadata | "json" -> el texto se parsea como JSON antes de dividir.

SPLITTERS: dict[str, dict[str, Any]] = {
    # ---------------------- SIN API KEY --------------------------------- #
    "lc_recursive": {
        "name": "RecursiveCharacterTextSplitter",
        "provider": "LangChain",
        "pricing": FREE_PRICING,
        "group": "no_api",
        "output": "text",
        "description": (
            "El splitter recomendado por LangChain para texto genérico. Prueba "
            "separadores en orden (párrafo → línea → espacio → carácter) y baja "
            "al siguiente solo si el trozo sigue siendo muy grande. Así mantiene "
            "juntos párrafos y oraciones. Mide en caracteres o en tokens."
        ),
        "params": [
            {"name": "length_unit", "label": "Medir el tamaño en", "type": "select", "default": "caracteres", "options": ["caracteres", "tokens"]},
            _SIZE_CHARS,
            _OVERLAP_CHARS,
        ],
        "factory": lambda p, _: _recursive(p),
    },
    "lc_character": {
        "name": "CharacterTextSplitter",
        "provider": "LangChain",
        "pricing": FREE_PRICING,
        "group": "no_api",
        "output": "text",
        "description": (
            "El más simple: corta por UN solo separador y vuelve a juntar los "
            "trozos hasta llenar el tamaño de chunk. Si un trozo entre separadores "
            "ya es más grande, queda tal cual (no lo subdivide)."
        ),
        "params": [
            {"name": "separator", "label": "Separador", "type": "select", "default": "párrafo (\\n\\n)", "options": list(_SEPARATORS)},
            _SIZE_CHARS,
            _OVERLAP_CHARS,
        ],
        "factory": lambda p, _: CharacterTextSplitter(
            separator=_SEPARATORS.get(str(p.get("separator")), "\n\n"),
            chunk_size=int(p.get("chunk_size", 1000)),
            chunk_overlap=int(p.get("chunk_overlap", 200)),
        ),
    },
    "lc_token": {
        "name": "TokenTextSplitter",
        "provider": "LangChain (tiktoken)",
        "pricing": FREE_PRICING,
        "group": "no_api",
        "output": "text",
        "description": (
            "Corta por un número fijo de tokens (tiktoken, cl100k_base) sin mirar "
            "oraciones ni párrafos. Útil para respetar con exactitud el límite de "
            "contexto de un modelo."
        ),
        "params": [
            {"name": "chunk_size", "label": "Tamaño de chunk (tokens)", "type": "int", "default": 256, "min": 32, "max": 2048, "step": 32},
            {"name": "chunk_overlap", "label": "Solapamiento (tokens)", "type": "int", "default": 20, "min": 0, "max": 512, "step": 8},
        ],
        "factory": lambda p, _: TokenTextSplitter(
            encoding_name="cl100k_base",
            chunk_size=int(p.get("chunk_size", 256)),
            chunk_overlap=int(p.get("chunk_overlap", 20)),
        ),
    },
    "lc_nltk": {
        "name": "NLTKTextSplitter",
        "provider": "LangChain (NLTK)",
        "pricing": FREE_PRICING,
        "group": "no_api",
        "output": "text",
        "description": (
            "Detecta oraciones con el tokenizador de NLTK (sabe, por ejemplo, que "
            "'Sr.' no cierra oración) y luego las agrupa hasta el tamaño de chunk. "
            "La primera vez descarga el modelo 'punkt_tab'."
        ),
        "params": [
            {"name": "language", "label": "Idioma", "type": "select", "default": "spanish", "options": ["spanish", "english", "portuguese", "french", "german", "italian"]},
            _SIZE_CHARS,
            _OVERLAP_CHARS,
        ],
        "factory": lambda p, _: _nltk(p),
    },
    "lc_markdown_header": {
        "name": "MarkdownHeaderTextSplitter",
        "provider": "LangChain",
        "pricing": FREE_PRICING,
        "group": "no_api",
        "output": "docs",
        "description": (
            "Corta un Markdown por sus encabezados (#, ##, ###) y guarda la ruta "
            "de encabezados de cada sección como metadata (H1, H2, ...). Esa "
            "metadata sirve después para filtrar o dar contexto en el retrieval."
        ),
        "params": [
            {"name": "max_level", "label": "Cortar hasta el nivel", "type": "select", "default": "3", "options": ["1", "2", "3", "4", "5", "6"]},
            {"name": "strip_headers", "label": "Quitar el encabezado del texto", "type": "select", "default": "no", "options": _YES_NO},
        ],
        "factory": lambda p, _: _markdown_headers(p),
    },
    "lc_html_header": {
        "name": "HTMLHeaderTextSplitter",
        "provider": "LangChain (BeautifulSoup)",
        "pricing": FREE_PRICING,
        "group": "no_api",
        "output": "docs",
        "description": (
            "Igual que el de Markdown pero para HTML: corta por <h1>, <h2>, ... y "
            "guarda los encabezados como metadata. Pega el HTML en bruto en el "
            "cuadro de texto."
        ),
        "params": [
            {"name": "max_level", "label": "Cortar hasta el nivel", "type": "select", "default": "3", "options": ["1", "2", "3", "4", "5", "6"]},
        ],
        "factory": lambda p, _: _html_headers(p),
    },
    "lc_code": {
        "name": "RecursiveCharacterTextSplitter.from_language",
        "provider": "LangChain",
        "pricing": FREE_PRICING,
        "group": "no_api",
        "output": "text",
        "description": (
            "El recursivo con los separadores propios de cada lenguaje (class, def, "
            "function, encabezados de Markdown, secciones de LaTeX...). No usa un "
            "AST como el CodeSplitter de LlamaIndex: trabaja con expresiones "
            "regulares, así que no necesita parsers."
        ),
        "params": [
            {"name": "language", "label": "Lenguaje", "type": "select", "default": "python", "options": [lang.value for lang in _CODE_LANGUAGES]},
            _SIZE_CHARS,
            {**_OVERLAP_CHARS, "default": 100},
        ],
        "factory": lambda p, _: RecursiveCharacterTextSplitter.from_language(
            Language(str(p.get("language", "python"))),
            chunk_size=int(p.get("chunk_size", 1000)),
            chunk_overlap=int(p.get("chunk_overlap", 100)),
        ),
    },
    "lc_json": {
        "name": "RecursiveJsonSplitter",
        "provider": "LangChain",
        "pricing": FREE_PRICING,
        "group": "no_api",
        "output": "json",
        "description": (
            "Divide un JSON recorriendo su árbol: cada chunk es un JSON válido que "
            "conserva la ruta de claves. Corta por objetos, no por caracteres. "
            "El texto de entrada debe ser JSON."
        ),
        "params": [
            {"name": "max_chunk_size", "label": "Tamaño máx. (caracteres)", "type": "int", "default": 300, "min": 50, "max": 8000, "step": 50},
        ],
        "factory": lambda p, _: RecursiveJsonSplitter(max_chunk_size=int(p.get("max_chunk_size", 300))),
    },
    # ------------- CON API KEY (embeddings: Google u OpenAI) ------------ #
    "lc_semantic": {
        "name": "SemanticChunker",
        "provider": "LangChain Experimental + embeddings (Google u OpenAI)",
        "pricing": SEMANTIC_PRICING,
        "group": "api",
        "output": "text",
        "description": (
            f"Corta donde cambia el tema: embebe las oraciones ({SEMANTIC_MODELS}) "
            "y abre un chunk nuevo cuando la distancia entre oraciones vecinas "
            "supera el umbral. Ofrece 4 criterios de umbral. Vive en "
            "langchain-experimental, que ya no tiene mantenimiento activo."
        ),
        "params": [
            {"name": "breakpoint_threshold_type", "label": "Criterio de umbral", "type": "select", "default": "percentile", "options": ["percentile", "standard_deviation", "interquartile", "gradient"]},
            {"name": "breakpoint_threshold_amount", "label": "Valor del umbral (0 = por defecto)", "type": "float", "default": 0, "min": 0, "max": 100, "step": 0.5},
            {"name": "buffer_size", "label": "Buffer (oraciones)", "type": "int", "default": 1, "min": 1, "max": 5, "step": 1},
        ],
        "factory": _semantic,
    },
}


def split(cfg: dict[str, Any], text: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Aplica una entrada del catálogo y devuelve los chunks."""
    embeddings = _get_embeddings() if cfg["group"] == "api" else None
    splitter = cfg["factory"](params, embeddings)

    if cfg["output"] == "json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"El texto no es un JSON válido: {exc}") from exc
        if not isinstance(data, dict):
            raise RuntimeError("RecursiveJsonSplitter necesita un objeto JSON ({...}), no una lista.")
        pieces = splitter.split_text(json_data=data, ensure_ascii=False)
        return [make_chunk(i, piece) for i, piece in enumerate(pieces)]

    if cfg["output"] == "docs":
        docs = [doc for doc in splitter.split_text(text) if doc.page_content.strip()]
        return [make_chunk(i, doc.page_content, metadata=doc.metadata) for i, doc in enumerate(docs)]

    return [make_chunk(i, piece) for i, piece in enumerate(splitter.split_text(text))]
