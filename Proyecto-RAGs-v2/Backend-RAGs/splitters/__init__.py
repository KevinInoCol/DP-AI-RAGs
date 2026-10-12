"""
Text Splitters (chunking) organizados por framework.

  splitters/llamaindex.py  -> Node Parsers de LlamaIndex (claves sin prefijo)
  splitters/langchain.py   -> Text Splitters de LangChain (claves con prefijo `lc_`)
  splitters/common.py      -> conteo de tokens y formato de chunk compartidos

Cada catálogo vive en su módulo y no importa al otro. Este paquete los une para
la API: `list_splitters` marca cada técnica con su `framework` y `split_text`
despacha al módulo que corresponde.
"""

from __future__ import annotations

from typing import Any

from . import langchain, llamaindex
from .common import count_tokens

# --------------------------------------------------------------------------- #
# Constantes
# --------------------------------------------------------------------------- #
# Orden en que se muestran en la UI.
FRAMEWORKS: dict[str, dict[str, Any]] = {
    "llamaindex": {"name": "LlamaIndex", "module": llamaindex},
    "langchain": {"name": "LangChain", "module": langchain},
}

__all__ = ["FRAMEWORKS", "count_tokens", "list_frameworks", "list_splitters", "split_text"]


def _find(key: str) -> tuple[str, dict[str, Any]]:
    for fw_key, fw in FRAMEWORKS.items():
        if key in fw["module"].SPLITTERS:
            return fw_key, fw["module"].SPLITTERS[key]
    raise KeyError(f"Splitter desconocido: {key}")


def list_frameworks() -> list[dict[str, str]]:
    """Frameworks en el orden en que se agrupan en la UI."""
    return [{"key": k, "name": fw["name"]} for k, fw in FRAMEWORKS.items()]


def list_splitters(framework: str | None = None) -> list[dict[str, Any]]:
    """Catálogo (sin las funciones factory) para el frontend.

    Con `framework` devuelve solo las técnicas de ese framework.
    """
    out = []
    for fw_key, fw in FRAMEWORKS.items():
        if framework and fw_key != framework:
            continue
        for key, cfg in fw["module"].SPLITTERS.items():
            out.append(
                {
                    "key": key,
                    "name": cfg["name"],
                    "framework": fw_key,
                    "framework_name": fw["name"],
                    "provider": cfg["provider"],
                    "pricing": cfg["pricing"],
                    "group": cfg["group"],
                    "description": cfg["description"],
                    "params": cfg["params"],
                    "requires_api_key": cfg["group"] == "api",
                }
            )
    return out


def split_text(key: str, text: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Aplica el splitter indicado y devuelve la lista de chunks resultante."""
    fw_key, cfg = _find(key)
    if not text or not text.strip():
        return []
    return FRAMEWORKS[fw_key]["module"].split(cfg, text, params or {})
