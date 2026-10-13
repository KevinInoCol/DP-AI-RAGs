"""
Utilidades compartidas por los catálogos de splitters (LlamaIndex y LangChain).

- `count_tokens`: misma medida de tokens para todos los frameworks, así las
  estadísticas de la UI son comparables entre técnicas.
- `make_chunk`: forma única del chunk que devuelve `/split`.
- Textos de precio/modelos de los splitters semánticos, armados desde el catálogo
  de embeddings para que no se desincronicen.
"""

from __future__ import annotations

from typing import Any

import tiktoken
from componentes.embeddings import EMBEDDERS, PROVIDER_PRIORITY

# --------------------------------------------------------------------------- #
# Constantes
# --------------------------------------------------------------------------- #
_ENCODER = tiktoken.get_encoding("cl100k_base")

FREE_PRICING = {"kind": "free", "label": "Gratis (local)"}

# Modelos y precios de embeddings (para los splitters semánticos de ambos frameworks).
SEMANTIC_MODELS = " o ".join(EMBEDDERS[k]["model"] for k in PROVIDER_PRIORITY)
SEMANTIC_PRICING = {
    "kind": "paid",
    "label": " · ".join(
        f"{EMBEDDERS[k]['provider']} {EMBEDDERS[k]['pricing']['label']}" for k in PROVIDER_PRIORITY
    ),
    "note": (
        "El corte es local, pero cada oración se embebe con el mismo modelo "
        "que la indexación."
    ),
}


def count_tokens(text: str) -> int:
    """Cuenta tokens aproximados (codificación cl100k_base, la de OpenAI)."""
    return len(_ENCODER.encode(text or ""))


def make_chunk(
    index: int,
    text: str,
    window: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Arma un chunk con el formato que consume el frontend."""
    return {
        "index": index,
        "text": text,
        "char_count": len(text),
        "token_count": count_tokens(text),
        "window": window,
        "metadata": metadata or None,
    }
