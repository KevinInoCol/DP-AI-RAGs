"""
Modelos de las peticiones JSON de la API.

En los requests, `embedder=None` significa "resuélvelo tú por la API key
disponible" (Google u OpenAI). Ver componentes/embeddings · resolve_embedder.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from pipeline.etapas.e03_ocr import DEFAULT_OCR_ENGINE


class SplitRequest(BaseModel):
    splitter: str
    text: str
    params: dict[str, Any] = {}


class EmbedRequest(BaseModel):
    embedder: str | None = None
    texts: list[str]
    params: dict[str, Any] = {}


class IndexRequest(BaseModel):
    embedder: str | None = None
    chunks: list[str]
    params: dict[str, Any] = {}


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class BenchmarkRequest(BaseModel):
    embedder: str | None = None
    embed_params: dict[str, Any] = {}
    chunks: list[str]
    queries: list[str]
    top_k: int = 5
    synthetic_scale: int = 5000
    store_params: dict[str, Any] = {}


class GcsIngestRequest(BaseModel):
    tenant: str
    bucket: str
    prefix: str = ""
    ocr_engine: str = DEFAULT_OCR_ENGINE
    embedder: str | None = None
    splitter: str | None = None
    loader: str | None = None
