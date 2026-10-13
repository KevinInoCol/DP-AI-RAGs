"""
Vector stores: dónde se guardan y se buscan los vectores.

  qdrant.py     · cliente de Qdrant compartido (banco e ingesta)
  benchmark.py  · fuerza bruta vs. HNSW, solo para la pestaña Vector Store
"""

from .benchmark import benchmark, list_stores
from .qdrant import qdrant_client

__all__ = ["benchmark", "list_stores", "qdrant_client"]
