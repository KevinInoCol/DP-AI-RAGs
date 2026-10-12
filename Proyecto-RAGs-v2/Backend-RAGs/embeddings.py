"""
Etapa de INDEXACIÓN del pipeline RAG: chunks -> vectores -> índice consultable.

Este módulo cubre tres cosas:

  1. Un CATÁLOGO de modelos de embedding (igual que loaders.py / splitters.py),
     para poder comparar opciones desde la UI. Hoy hay DOS proveedores:
       - gemini-embedding-2        (Google · GOOGLE_API_KEY)
       - text-embedding-3-small    (OpenAI · OPENAI_API_KEY)
     Ambos se acceden a través de LlamaIndex, así que la interfaz es idéntica.

  2. RESOLUCIÓN AUTOMÁTICA por API key disponible (`resolve_embedder`): el sistema
     elige el proveedor mirando qué claves hay en el entorno, siguiendo el orden de
     PROVIDER_PRIORITY. Así el testbed y el pipeline de ingesta funcionan con
     cualquiera de las dos claves, sin tocar código.

  3. Un ÍNDICE VECTORIAL en memoria (cosine) para probar la etapa completa:
     se indexan los chunks (task_type de documento) y luego se consulta con una
     pregunta (task_type de query). Así el testbed demuestra retrieval real.

Notas de diseño
---------------
- Todo pasa por LlamaIndex (coherencia con loaders/splitters). Los dos wrappers
  exponen `get_text_embedding_batch` (documentos) y `get_query_embedding` (query),
  así que el código de embedding es UNO para ambos proveedores.
- RETRIEVAL ASIMÉTRICO: Gemini SÍ lo aplica (el wrapper manda RETRIEVAL_DOCUMENT
  vs. RETRIEVAL_QUERY según el método). Los modelos text-embedding-3-* de OpenAI
  son SIMÉTRICOS: no hay task_type, documento y query se embeben igual. No es un
  bug — es una diferencia real entre los modelos (campo `asymmetric` del catálogo).
- TRUNCADO DE DIMENSIONES: los dos modelos lo soportan (Gemini con Matryoshka/MRL,
  OpenAI con el parámetro `dimensions`), y en LOS DOS casos el vector truncado deja
  de estar normalizado. Por eso aquí SIEMPRE normalizamos con `_l2_normalize`, o el
  coseno saldría mal.

⚠️ CONTRATO DE INTEGRACIÓN: el agente que CONSULTE la base DEBE usar el MISMO
modelo + dimensión con que se indexó. Los espacios vectoriales de Gemini y OpenAI
NO son compatibles entre sí (ni distintas dimensiones del mismo modelo): cambiar de
proveedor obliga a RE-EMBEBER todo. Por eso `resolve_embedder` nunca cambia de
modelo en silencio cuando se le pide uno explícito: falla con un error claro.
"""

from __future__ import annotations

import os
import time
from typing import Any

import numpy as np

# --------------------------------------------------------------------------- #
# Modelos por proveedor · FUENTE DE VERDAD (cambiarlos aquí = una línea)
# --------------------------------------------------------------------------- #
# gemini-embedding-2: GA, primer modelo multimodal de Google, 3072 nativo + MRL.
GEMINI_MODEL = "gemini-embedding-2"
GEMINI_DIMENSION = 768          # default (MRL: 768/1536/3072 = el mismo vector truncado)
# Precio de lista (texto, tier de pago): https://ai.google.dev/gemini-api/docs/pricing
GEMINI_USD_PER_1M_TOKENS = 0.20

# text-embedding-3-small: 1536 nativo, admite truncado vía `dimensions`.
OPENAI_MODEL = "text-embedding-3-small"
OPENAI_DIMENSION = 1536         # default = nativo (sin truncar)
# Precio de lista: https://platform.openai.com/docs/pricing
OPENAI_USD_PER_1M_TOKENS = 0.02

# Orden de preferencia cuando hay MÁS DE UNA API key disponible.
# Google primero: las colecciones Qdrant ya ingestadas se crearon con Gemini/768,
# y cambiar el default las volvería incompatibles.
PROVIDER_PRIORITY = ("gemini", "openai")


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    """Normaliza cada fila a norma 1 (con guarda para vectores nulos).

    Necesario tras truncar dimensiones en AMBOS proveedores (Gemini/MRL y OpenAI
    /`dimensions`): solo el vector completo viene normalizado. Normalizar uno ya
    normalizado es un no-op seguro.
    """
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return vectors / norms


def _require_key(key: str) -> str:
    """Devuelve la API key del proveedor o falla con un mensaje accionable."""
    cfg = EMBEDDERS[key]
    env = cfg["requires_env"]
    api_key = os.getenv(env)
    if not api_key:
        raise RuntimeError(
            f"Falta {env}. Consíguela en {cfg['api_key_url']} y colócala en el "
            f"archivo .env para usar {cfg['model']}."
        )
    return api_key


# --------------------------------------------------------------------------- #
# Constructores del modelo de LlamaIndex (uno por proveedor)
# --------------------------------------------------------------------------- #
def _gemini_model(params: dict[str, Any]):
    """gemini-embedding-2 (Google) vía LlamaIndex (GoogleGenAIEmbedding).

    La dimensión (MRL) se pasa por `embedding_config`. El task_type lo aplica el
    wrapper según el método: documentos vs. query (retrieval asimétrico).
    """
    api_key = _require_key("gemini")
    from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

    dimension = int(params.get("dimension", GEMINI_DIMENSION))
    return GoogleGenAIEmbedding(
        model_name=GEMINI_MODEL,
        api_key=api_key,
        embedding_config={"output_dimensionality": dimension},
    )


def _openai_model(params: dict[str, Any]):
    """text-embedding-3-small (OpenAI) vía LlamaIndex (OpenAIEmbedding).

    La dimensión se pasa por `dimensions` (la API la trunca del vector de 1536).
    No hay task_type: el modelo es simétrico.
    """
    api_key = _require_key("openai")
    from llama_index.embeddings.openai import OpenAIEmbedding

    dimension = int(params.get("dimension", OPENAI_DIMENSION))
    return OpenAIEmbedding(
        model=OPENAI_MODEL,
        api_key=api_key,
        dimensions=dimension,
    )


def _run_embed(model, texts: list[str], is_query: bool) -> np.ndarray:
    """Embebe con el modelo de LlamaIndex ya construido. Común a los dos proveedores:
    el wrapper decide el task_type (Gemini) o lo ignora (OpenAI, simétrico)."""
    if is_query:
        vectors = [model.get_query_embedding(t) for t in texts]  # RETRIEVAL_QUERY
    else:
        vectors = model.get_text_embedding_batch(texts, show_progress=False)  # RETRIEVAL_DOCUMENT
    return _l2_normalize(np.array(vectors, dtype=np.float32))


# --------------------------------------------------------------------------- #
# Catálogo
# --------------------------------------------------------------------------- #
EMBEDDERS: dict[str, dict[str, Any]] = {
    "gemini": {
        "name": "gemini-embedding-2 (Google)",
        "group": "api",
        "provider": "Google",
        "model": GEMINI_MODEL,
        "usd_per_1m_tokens": GEMINI_USD_PER_1M_TOKENS,
        "pricing": {
            "kind": "paid",
            "label": f"${GEMINI_USD_PER_1M_TOKENS:.2f} / 1M tokens",
            "note": (
                "Tier gratis con límites de uso; en ese tier Google puede usar los "
                "datos para mejorar sus productos. Para datos corporativos, tier de pago."
            ),
        },
        "requires_env": "GOOGLE_API_KEY",
        "api_key_url": "https://aistudio.google.com/apikey",
        "asymmetric": True,
        "native_dimension": 3072,
        "description": (
            "Modelo de Google (GA · primer multimodal), vía LlamaIndex "
            "(GoogleGenAIEmbedding). Multilingüe (100+ idiomas, muy bueno en español) "
            "y con Matryoshka (MRL): elige 768/1536/3072 dims según tu trade-off "
            "calidad↔costo. El retrieval ASIMÉTRICO (documento vs. query) lo aplica "
            "LlamaIndex automáticamente. Aquí embebemos texto extraído del PDF."
        ),
        "params": [
            {
                "name": "dimension",
                "label": "Dimensión del vector (MRL)",
                "type": "select",
                "default": GEMINI_DIMENSION,
                "options": [768, 1536, 3072],
            },
        ],
        "model_factory": _gemini_model,
    },
    "openai": {
        "name": "text-embedding-3-small (OpenAI)",
        "group": "api",
        "provider": "OpenAI",
        "model": OPENAI_MODEL,
        "usd_per_1m_tokens": OPENAI_USD_PER_1M_TOKENS,
        "pricing": {
            "kind": "paid",
            "label": f"${OPENAI_USD_PER_1M_TOKENS:.2f} / 1M tokens",
            "note": (
                "Sin tier gratis. Por defecto OpenAI no usa los datos de la API "
                "para entrenar sus modelos."
            ),
        },
        "requires_env": "OPENAI_API_KEY",
        "api_key_url": "https://platform.openai.com/api-keys",
        "asymmetric": False,
        "native_dimension": 1536,
        "description": (
            "El modelo de embeddings económico de OpenAI (1536 dims nativas), vía "
            "LlamaIndex (OpenAIEmbedding). Muy barato y rápido, buen multilingüe. "
            "Admite truncar dimensiones con `dimensions` (512/1024/1536) para "
            "ahorrar espacio en el vector store. OJO: es un modelo SIMÉTRICO — no "
            "distingue documento de query, a diferencia de Gemini."
        ),
        "params": [
            {
                "name": "dimension",
                "label": "Dimensión del vector",
                "type": "select",
                "default": OPENAI_DIMENSION,
                "options": [512, 1024, 1536],
            },
        ],
        "model_factory": _openai_model,
    },
}


# --------------------------------------------------------------------------- #
# Resolución del proveedor según la API key disponible
# --------------------------------------------------------------------------- #
def has_api_key(key: str) -> bool:
    """True si la API key del proveedor está definida en el entorno."""
    if key not in EMBEDDERS:
        return False
    return bool(os.getenv(EMBEDDERS[key]["requires_env"]))


def available_embedders() -> list[str]:
    """Claves de los embedders USABLES ahora mismo, en orden de preferencia."""
    return [k for k in PROVIDER_PRIORITY if has_api_key(k)]


def default_embedder() -> str | None:
    """El embedder que se usaría automáticamente, o None si no hay ninguna key."""
    available = available_embedders()
    return available[0] if available else None


def resolve_embedder(preferred: str | None = None) -> str:
    """Decide QUÉ embedder usar.

    - `preferred=None`  -> el primero disponible según PROVIDER_PRIORITY.
    - `preferred="x"`   -> ese, si su API key está presente.

    Nunca cambia de proveedor en silencio: si pides uno explícito y no tiene key,
    falla (cambiar de modelo invalidaría los vectores ya indexados).

    Raises:
      KeyError:     el embedder pedido no existe en el catálogo.
      RuntimeError: no hay API key (ni la pedida, ni ninguna).
    """
    if preferred:
        if preferred not in EMBEDDERS:
            raise KeyError(f"Embedder desconocido: {preferred}")
        if not has_api_key(preferred):
            cfg = EMBEDDERS[preferred]
            raise RuntimeError(
                f"Falta {cfg['requires_env']} para usar {cfg['name']}. "
                f"Consíguela en {cfg['api_key_url']} y colócala en el archivo .env."
            )
        return preferred

    auto = default_embedder()
    if auto is None:
        envs = " o ".join(cfg["requires_env"] for cfg in EMBEDDERS.values())
        raise RuntimeError(
            f"No hay ninguna API key de embeddings configurada. Define {envs} "
            "en el archivo .env (basta UNA de las dos)."
        )
    return auto


def llama_embed_model(key: str | None = None, params: dict[str, Any] | None = None):
    """Devuelve el objeto de embeddings de LlamaIndex del proveedor resuelto.

    Lo consumen los componentes de LlamaIndex que necesitan un `embed_model`
    (p. ej. SemanticSplitterNodeParser en splitters.py).
    """
    resolved = resolve_embedder(key)
    return EMBEDDERS[resolved]["model_factory"](params or {})


def embedding_dimension(key: str | None = None, params: dict[str, Any] | None = None) -> int:
    """Dimensión que producirá el embedder resuelto con esos params (sin llamar a
    la API). La usa el pipeline para crear la colección de Qdrant."""
    resolved = resolve_embedder(key)
    cfg = EMBEDDERS[resolved]
    default = cfg["params"][0]["default"]
    return int((params or {}).get("dimension", default))


def list_embedders() -> list[dict[str, Any]]:
    """Catálogo (sin funciones) para construir el menú del frontend.

    Incluye `available` (¿está su API key?) y `is_default` (el que se usaría en
    automático) para que la UI pueda deshabilitar y preseleccionar sola.
    """
    auto = default_embedder()
    out = []
    for key, cfg in EMBEDDERS.items():
        out.append(
            {
                "key": key,
                "name": cfg["name"],
                "group": cfg["group"],
                "provider": cfg["provider"],
                "model": cfg["model"],
                "pricing": cfg["pricing"],
                "description": cfg["description"],
                "params": cfg["params"],
                "requires_api_key": cfg["group"] == "api",
                "requires_env": cfg["requires_env"],
                "api_key_url": cfg["api_key_url"],
                "asymmetric": cfg["asymmetric"],
                "native_dimension": cfg["native_dimension"],
                "available": has_api_key(key),
                "is_default": key == auto,
            }
        )
    return out


# --------------------------------------------------------------------------- #
# API de embedding
# --------------------------------------------------------------------------- #
def _embed(key: str | None, texts: list[str], params: dict[str, Any], is_query: bool) -> np.ndarray:
    resolved = resolve_embedder(key)
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    model = EMBEDDERS[resolved]["model_factory"](params or {})
    return _run_embed(model, texts, is_query)


def embed_documents(key: str | None, texts: list[str], params: dict[str, Any] | None = None) -> np.ndarray:
    """Embebe textos como DOCUMENTOS (para indexar). Devuelve una matriz (N, dim).
    `key=None` -> resuelve el proveedor por API key disponible."""
    return _embed(key, texts, params or {}, is_query=False)


def embed_query(key: str | None, text: str, params: dict[str, Any] | None = None) -> np.ndarray:
    """Embebe una query. Devuelve un vector (dim,)."""
    return _embed(key, [text], params or {}, is_query=True)[0]


# --------------------------------------------------------------------------- #
# Inspección de embeddings (para la UI de comparación)
# --------------------------------------------------------------------------- #
def embed_texts(key: str | None, texts: list[str], params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Embebe una lista de textos (como DOCUMENTOS) y devuelve stats + preview.

    No devuelve los vectores completos (serían cientos de floats por chunk):
    solo dimensión, norma y los primeros valores, que es lo que se visualiza.
    """
    resolved = resolve_embedder(key)
    t0 = time.perf_counter()
    vectors = _embed(resolved, texts, params or {}, is_query=False)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    dim = int(vectors.shape[1]) if vectors.size else 0
    items = [
        {
            "index": i,
            "text_preview": (t[:120] + "…") if len(t) > 120 else t,
            "norm": round(float(np.linalg.norm(vectors[i])), 4),
            "preview": [round(float(x), 4) for x in vectors[i][:8]],
        }
        for i, t in enumerate(texts)
    ]
    return {
        "embedder": resolved,
        "model": EMBEDDERS[resolved]["model"],
        "dimension": dim,
        "count": len(texts),
        "elapsed_ms": elapsed_ms,
        "vectors": items,
    }


# --------------------------------------------------------------------------- #
# Índice vectorial en memoria (indexar + consultar)
# --------------------------------------------------------------------------- #
class VectorIndex:
    """Índice coseno en memoria. Suficiente para el testbed; en producción esto
    sería Qdrant / pgvector, pero la interfaz (build/search) es la misma.

    El embedder se RESUELVE al construir y se guarda: así la query se embebe con
    el MISMO modelo y dimensión que los documentos (si no, el coseno no significa
    nada)."""

    def __init__(self, key: str | None, params: dict[str, Any]):
        self.key = resolve_embedder(key)
        self.params = params or {}
        self.vectors: np.ndarray = np.zeros((0, 0), dtype=np.float32)
        self.chunks: list[dict[str, Any]] = []

    def build(self, chunks: list[dict[str, Any]]) -> None:
        """chunks: [{text, metadata?}]. Los embebe como DOCUMENTOS y los guarda."""
        texts = [c["text"] for c in chunks]
        self.vectors = _embed(self.key, texts, self.params, is_query=False)
        self.chunks = chunks

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Embebe la query (task_type de QUERY) y devuelve los top_k por coseno.

        Como todos los vectores están L2-normalizados, el coseno es el producto
        punto: una sola multiplicación matricial.
        """
        if not self.chunks:
            return []
        q = _embed(self.key, [query], self.params, is_query=True)[0]
        scores = self.vectors @ q  # (N,) — coseno porque están normalizados
        top = np.argsort(-scores)[: max(1, top_k)]
        return [
            {
                "rank": rank + 1,
                "score": round(float(scores[i]), 4),
                "index": int(i),
                "text": self.chunks[int(i)]["text"],
                "metadata": self.chunks[int(i)].get("metadata", {}),
            }
            for rank, i in enumerate(top)
        ]


def build_index(key: str | None, chunks: list[dict[str, Any]], params: dict[str, Any] | None = None) -> VectorIndex:
    """Atajo: crea un VectorIndex y lo llena con los chunks dados."""
    index = VectorIndex(key, params or {})
    index.build(chunks)
    return index
