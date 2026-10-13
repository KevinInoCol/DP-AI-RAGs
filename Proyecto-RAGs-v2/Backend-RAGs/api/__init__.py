"""
Capa HTTP (FastAPI). Solo traduce peticiones a llamadas a componentes/ y pipeline/:
aquí no hay lógica de RAG.

  schemas.py          · modelos de las peticiones JSON
  routers/banco.py    · banco de pruebas: loaders, splitters, embeddings, vector stores
  routers/pipeline.py · descripción del pipeline para la pestaña (GET /pipeline)
  routers/ingesta.py  · ingesta real: subida directa y bucket de GCS (SSE)
  routers/sistema.py  · /health y /extract
"""
