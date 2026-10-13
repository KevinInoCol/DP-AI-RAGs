"""
API FastAPI del RAG Toolkit: banco de pruebas (loaders, splitters, embeddings,
vector stores) y pipeline de ingesta a Qdrant.

Este archivo solo arma la aplicación: CORS y routers. Los endpoints viven en
api/routers/, uno por área de la UI:

  banco.py     GET  /loaders · POST /load · GET /splitters · POST /split
               GET  /embedders · POST /embed · POST /index · POST /search
               GET  /vectorstores · POST /vectorstores/benchmark
  pipeline.py  GET  /pipeline · GET /ocr-engines
  ingesta.py   POST /ingest · GET /gcs/pdfs · POST /ingest/gcs   (SSE)
  sistema.py   GET  /health · POST /extract

La documentación interactiva queda en http://localhost:8005/docs.

Ejecutar:
  uvicorn main:app --reload --port 8005
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config  # noqa: F401 · carga el .env antes que cualquier otro módulo
from api.routers import banco, ingesta, pipeline, sistema

app = FastAPI(title="RAG Toolkit · Testbed e ingesta", version="1.2.0")

# CORS abierto para desarrollo (frontend en Vite: 5174, con proxy /api).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sistema.router)
app.include_router(banco.router)
app.include_router(pipeline.router)
app.include_router(ingesta.router)
