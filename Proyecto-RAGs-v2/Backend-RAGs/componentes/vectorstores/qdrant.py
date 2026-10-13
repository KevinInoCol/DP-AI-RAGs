"""
Cliente de QDRANT compartido: lo usan el benchmark del banco (benchmark.py) y la
ingesta (pipeline/etapas/e09_indexado.py). Credenciales en config.py
(QDRANT_URL y QDRANT_API_KEY).
"""

from __future__ import annotations

from typing import Any

import config


def qdrant_client():
    """Cliente de Qdrant a partir de QDRANT_URL / QDRANT_API_KEY (.env).

    Si la URL es https sin puerto explícito (típico de despliegues detrás de un
    proxy, p.ej. easypanel), qdrant-client asumiría el 6333 y daría "connection
    refused". En ese caso forzamos el puerto 443.
    """
    url = config.QDRANT_URL
    if not url:
        raise RuntimeError(
            "Falta QDRANT_URL. Define en .env la URL de tu servidor Qdrant "
            "(y QDRANT_API_KEY si aplica) para usar los motores de Qdrant."
        )
    from urllib.parse import urlparse

    from qdrant_client import QdrantClient

    kwargs: dict[str, Any] = {"url": url, "api_key": config.QDRANT_API_KEY, "timeout": 120}
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.port is None:
        kwargs["port"] = 443
    return QdrantClient(**kwargs)
