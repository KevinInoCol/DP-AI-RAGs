"""
Etapa de VECTOR STORE: comparar cómo se INDEXAN y BUSCAN los vectores.

El eje de comparación es Fuerza Bruta (exacto) vs. ANN (aproximado), y el motor
real es **Qdrant** (base de datos vectorial, corre como servicio; credenciales en
.env: QDRANT_URL y QDRANT_API_KEY):

  - numpy_flat    -> fuerza bruta en numpy (exacto, en proceso). Baseline sin infra.
  - qdrant_exact  -> Qdrant con HNSW DESACTIVADO (m=0) -> full scan exacto.
  - qdrant_hnsw   -> Qdrant con índice HNSW (ANN). Params M / ef_search.

Qdrant hace las dos cosas: la MISMA base de datos puede buscar exacto (exact=true,
recorre todo) o aproximado (HNSW). Aquí usamos dos colecciones distintas para que
el coste de CONSTRUIR el índice también sea comparable (HNSW paga por adelantado).

La comparación mide el trade-off completo:
  - build_ms       : coste de CONSTRUIR el índice (lado izquierdo / escritura).
  - avg_search_ms  : coste de BUSCAR (lado derecho / consulta del agente).
  - recall@k       : fracción de los "verdaderos" vecinos que recupera cada motor,
                     medida contra la búsqueda exacta (los exactos dan 1.0; el HNSW
                     suele dar <1.0 — eso es lo que se paga por la velocidad).

Para que el trade-off sea VISIBLE con documentos pequeños, el benchmark rellena el
índice con vectores sintéticos (aleatorios, normalizados). No cambian la validez del
recall (se mide contra el exacto sobre el MISMO conjunto), solo llevan el índice a
una escala donde ANN vs. exacto se nota.

Todos los vectores llegan ya L2-normalizados desde embeddings.py; usamos distancia
COSINE en Qdrant.
"""

from __future__ import annotations

import os
import time
from typing import Any

import numpy as np

from embeddings import embed_documents, embed_query


# --------------------------------------------------------------------------- #
# Conexión a Qdrant
# --------------------------------------------------------------------------- #
def _qdrant_client():
    """Cliente de Qdrant a partir de QDRANT_URL / QDRANT_API_KEY (.env).

    Si la URL es https sin puerto explícito (típico de despliegues detrás de un
    proxy, p.ej. easypanel), qdrant-client asumiría el 6333 y daría "connection
    refused". En ese caso forzamos el puerto 443.
    """
    url = os.getenv("QDRANT_URL")
    if not url:
        raise RuntimeError(
            "Falta QDRANT_URL. Define en .env la URL de tu servidor Qdrant "
            "(y QDRANT_API_KEY si aplica) para usar los motores de Qdrant."
        )
    from urllib.parse import urlparse

    from qdrant_client import QdrantClient

    kwargs: dict[str, Any] = {"url": url, "api_key": os.getenv("QDRANT_API_KEY"), "timeout": 120}
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.port is None:
        kwargs["port"] = 443
    return QdrantClient(**kwargs)


# --------------------------------------------------------------------------- #
# Motores de índice (interfaz común: build / search / cleanup)
# --------------------------------------------------------------------------- #
class NumpyFlatStore:
    """Fuerza bruta exacta en proceso: producto matricial contra todos los vectores."""

    kind = "exact"

    def __init__(self, params: dict[str, Any]):
        self.vectors = np.zeros((0, 0), dtype=np.float32)

    def build(self, vectors: np.ndarray) -> None:
        self.vectors = vectors

    def search(self, q: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
        scores = self.vectors @ q  # coseno (vectores normalizados)
        idx = np.argsort(-scores)[:top_k]
        return idx, scores[idx]

    def cleanup(self) -> None:
        pass


class QdrantStore:
    """Motor Qdrant. `use_hnsw=False` desactiva el índice (m=0) -> exacto/full scan;
    `use_hnsw=True` construye el grafo HNSW (ANN)."""

    def __init__(self, params: dict[str, Any], use_hnsw: bool, collection: str):
        self.params = params
        self.use_hnsw = use_hnsw
        self.collection = collection
        self.kind = "ann" if use_hnsw else "exact"
        self.ef_search = int(params.get("ef_search", 64))
        self.client = None

    def build(self, vectors: np.ndarray) -> None:
        from qdrant_client import models as qm

        client = _qdrant_client()
        self.client = client
        dim = int(vectors.shape[1])

        if self.use_hnsw:
            hnsw = qm.HnswConfigDiff(
                m=int(self.params.get("M", 16)),
                ef_construct=int(self.params.get("ef_construction", 100)),
            )
            # Forzar el indexado aunque haya pocos vectores (default es 20000).
            optimizers = qm.OptimizersConfigDiff(indexing_threshold=1)
        else:
            hnsw = qm.HnswConfigDiff(m=0)  # sin grafo -> full scan exacto
            optimizers = None

        try:
            client.delete_collection(self.collection)
        except Exception:  # noqa: BLE001  (no existía; da igual)
            pass
        client.create_collection(
            collection_name=self.collection,
            vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
            hnsw_config=hnsw,
            optimizers_config=optimizers,
        )

        BATCH = 1000
        for start in range(0, len(vectors), BATCH):
            batch = vectors[start : start + BATCH]
            points = [
                qm.PointStruct(id=start + i, vector=batch[i].tolist())
                for i in range(len(batch))
            ]
            client.upsert(collection_name=self.collection, points=points, wait=True)

        # Esperar a que Qdrant termine de optimizar/indexar (solo importa con HNSW).
        if self.use_hnsw:
            self._wait_indexed(client)

    def _wait_indexed(self, client, timeout: float = 120.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            info = client.get_collection(self.collection)
            status = getattr(info.status, "value", str(info.status)).lower()
            if status != "yellow":  # green/grey = optimización terminada
                return
            time.sleep(0.5)

    def search(self, q: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
        from qdrant_client import models as qm

        params = qm.SearchParams(hnsw_ef=self.ef_search, exact=not self.use_hnsw)
        res = self.client.query_points(
            collection_name=self.collection,
            query=q.tolist(),
            limit=top_k,
            search_params=params,
        ).points
        idx = np.array([p.id for p in res], dtype=np.int64)
        scores = np.array([p.score for p in res], dtype=np.float32)
        return idx, scores

    def cleanup(self) -> None:
        if self.client is not None:
            try:
                self.client.delete_collection(self.collection)
            except Exception:  # noqa: BLE001
                pass


# --------------------------------------------------------------------------- #
# Catálogo
# --------------------------------------------------------------------------- #
# Qdrant es open source (gratis si lo hospedas tú); Qdrant Cloud tiene plan gratis
# pequeño y planes de pago por recursos.
QDRANT_PRICING = {
    "kind": "freemium",
    "label": "Gratis self-hosted · Cloud de pago",
    "note": "Open source si lo hospedas tú; Qdrant Cloud cobra según el tamaño del cluster.",
}

VECTOR_STORES: dict[str, dict[str, Any]] = {
    "numpy_flat": {
        "name": "NumPy Flat (fuerza bruta)",
        "provider": "NumPy (open source)",
        "pricing": {"kind": "free", "label": "Gratis (local)"},
        "kind": "exact",
        "engine": "numpy · en proceso",
        "description": (
            "Fuerza bruta pura, en el mismo proceso Python: compara la query contra "
            "TODOS los vectores con una multiplicación matricial. Exacto y sin infra, "
            "pero no persiste ni escala. Es el baseline de referencia."
        ),
        "params": [],
        "factory": lambda p: NumpyFlatStore(p),
    },
    "qdrant_exact": {
        "name": "Qdrant · Exacto (fuerza bruta)",
        "provider": "Qdrant",
        "pricing": QDRANT_PRICING,
        "kind": "exact",
        "engine": "Qdrant · full scan (m=0)",
        "description": (
            "Qdrant con el índice HNSW desactivado (m=0): cada búsqueda recorre todos "
            "los vectores de la colección. Exacto, igual que el baseline, pero ya "
            "dentro de la base de datos (persistente, con filtros por metadata)."
        ),
        "params": [],
        "factory": lambda p: QdrantStore(p, use_hnsw=False, collection="rags_bench_exact"),
    },
    "qdrant_hnsw": {
        "name": "Qdrant · HNSW (ANN)",
        "provider": "Qdrant",
        "pricing": QDRANT_PRICING,
        "kind": "ann",
        "engine": "Qdrant · HNSW",
        "description": (
            "Qdrant con índice aproximado HNSW. Paga por adelantado al construir el "
            "grafo (indexar más lento) para que cada búsqueda sea rapidísima sin "
            "recorrer todo. Puede perder algún vecino real (recall <100%). Sube "
            "`ef_search` para más recall a costa de velocidad."
        ),
        "params": [
            {"name": "M", "label": "M (conexiones por nodo)", "type": "int", "default": 16, "min": 4, "max": 64, "step": 4},
            {"name": "ef_search", "label": "ef_search (amplitud de búsqueda)", "type": "int", "default": 64, "min": 4, "max": 512, "step": 4},
        ],
        "factory": lambda p: QdrantStore(p, use_hnsw=True, collection="rags_bench_hnsw"),
    },
}


def list_stores() -> list[dict[str, Any]]:
    """Catálogo (sin funciones) para el frontend."""
    return [
        {
            "key": key,
            "name": cfg["name"],
            "provider": cfg["provider"],
            "pricing": cfg["pricing"],
            "kind": cfg["kind"],
            "engine": cfg["engine"],
            "description": cfg["description"],
            "params": cfg["params"],
        }
        for key, cfg in VECTOR_STORES.items()
    ]


# --------------------------------------------------------------------------- #
# Benchmark: construye cada motor, mide y compara contra el exacto
# --------------------------------------------------------------------------- #
def _random_normalized(n: int, dim: int, seed: int = 42) -> np.ndarray:
    """n vectores aleatorios (gaussianos) L2-normalizados, para escalar el índice."""
    rng = np.random.default_rng(seed)
    v = rng.standard_normal((n, dim)).astype(np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return v


def benchmark(
    embedder: str,
    embed_params: dict[str, Any],
    chunks: list[str],
    queries: list[str],
    top_k: int = 5,
    synthetic_scale: int = 5000,
    store_params: dict[str, Any] | None = None,
    store_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Ejecuta la comparación Fuerza Bruta vs. ANN y devuelve métricas por motor."""
    store_params = store_params or {}
    store_keys = store_keys or list(VECTOR_STORES.keys())
    chunks = [c for c in (chunks or []) if c.strip()]
    queries = [q for q in (queries or []) if q.strip()]
    if not chunks:
        raise ValueError("Necesitas al menos un chunk para indexar.")
    if not queries:
        raise ValueError("Necesitas al menos una consulta para comparar.")

    # 1) Embeber chunks reales (documentos) y queries. Una sola llamada por lado.
    real = embed_documents(embedder, chunks, embed_params)  # (K, dim)
    K, dim = real.shape
    qvecs = np.ascontiguousarray(
        np.array([embed_query(embedder, q, embed_params) for q in queries], dtype=np.float32)
    )

    # 2) Rellenar con vectores sintéticos para que la escala haga visible el trade-off.
    synthetic_scale = max(0, min(int(synthetic_scale), 50000))
    if synthetic_scale:
        all_vecs = np.ascontiguousarray(np.vstack([real, _random_normalized(synthetic_scale, dim)]))
    else:
        all_vecs = np.ascontiguousarray(real)
    n_vectors = all_vecs.shape[0]
    k = max(1, min(int(top_k), n_vectors))

    # 3) Ground truth: top-k exacto por query (referencia para el recall).
    gt = []
    for q in qvecs:
        scores = all_vecs @ q
        gt.append(set(np.argsort(-scores)[:k].tolist()))

    # 4) Cada motor: construir (una vez) + buscar (todas las queries) + recall.
    results = []
    for key in store_keys:
        cfg = VECTOR_STORES[key]
        store = cfg["factory"](store_params)
        try:
            t0 = time.perf_counter()
            store.build(all_vecs)
            build_ms = round((time.perf_counter() - t0) * 1000, 2)

            search_times = []
            recalls = []
            first_hits = None
            for qi, q in enumerate(qvecs):
                t1 = time.perf_counter()
                idx, scores = store.search(q, k)
                search_times.append((time.perf_counter() - t1) * 1000)
                found = {int(i) for i in idx if i >= 0}
                recalls.append(len(found & gt[qi]) / len(gt[qi]))
                if qi == 0:
                    first_hits = list(zip((int(i) for i in idx), (float(s) for s in scores)))

            results.append({
                "key": key,
                "name": cfg["name"],
                "kind": cfg["kind"],
                "engine": cfg["engine"],
                "status": "ok",
                "build_ms": build_ms,
                "avg_search_ms": round(sum(search_times) / len(search_times), 3),
                "recall": round(sum(recalls) / len(recalls), 4),
                "hits": _describe_hits(first_hits, chunks, K),
            })
        except RuntimeError as exc:  # falta QDRANT_URL, etc.
            results.append({
                "key": key, "name": cfg["name"], "kind": cfg["kind"], "engine": cfg["engine"],
                "status": "error", "message": str(exc),
            })
        except ImportError:
            results.append({
                "key": key, "name": cfg["name"], "kind": cfg["kind"], "engine": cfg["engine"],
                "status": "error",
                "message": "qdrant-client no está instalado. Instálalo con: pip install qdrant-client",
            })
        except Exception as exc:  # noqa: BLE001
            results.append({
                "key": key, "name": cfg["name"], "kind": cfg["kind"], "engine": cfg["engine"],
                "status": "error", "message": f"{type(exc).__name__}: {exc}",
            })
        finally:
            store.cleanup()

    return {
        "embedder": embedder,
        "dimension": dim,
        "num_real_chunks": K,
        "num_vectors": n_vectors,
        "synthetic_scale": synthetic_scale,
        "top_k": k,
        "num_queries": len(queries),
        "query": queries[0],
        "results": results,
    }


def _describe_hits(hits, chunks: list[str], k_real: int) -> list[dict[str, Any]]:
    """Convierte los (idx, score) del top-k de la 1ª query en algo legible:
    si el índice cae en un chunk real muestra su texto; si es sintético lo marca."""
    if not hits:
        return []
    out = []
    for rank, (idx, score) in enumerate(hits):
        if 0 <= idx < k_real:
            text = chunks[idx]
            preview = (text[:160] + "…") if len(text) > 160 else text
            out.append({"rank": rank + 1, "score": round(score, 4), "kind": "chunk", "text": preview})
        else:
            out.append({"rank": rank + 1, "score": round(score, 4), "kind": "synthetic",
                        "text": f"(vector sintético #{idx})"})
    return out
