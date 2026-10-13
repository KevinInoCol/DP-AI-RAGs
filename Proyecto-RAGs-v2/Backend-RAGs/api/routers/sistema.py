"""
Rutas de sistema: estado del servicio y extracción rápida de texto de un archivo
(la usa la pestaña Text Splitters para cargar un documento de prueba).
"""

from __future__ import annotations

import io
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

import config
from componentes.embeddings import available_embedders, default_embedder

router = APIRouter(tags=["sistema"])


@router.get("/health")
def health() -> dict[str, Any]:
    """Estado del servicio + qué proveedores de embeddings están usables ahora."""
    return {
        "status": "ok",
        "google_key_loaded": bool(config.GOOGLE_API_KEY),
        "openai_key_loaded": bool(config.OPENAI_API_KEY),
        "embedders_available": available_embedders(),
        "embedder_default": default_embedder(),
    }


@router.post("/extract")
async def post_extract(file: UploadFile = File(...)) -> dict[str, Any]:
    """Extrae texto plano de un archivo subido (.txt, .md, .pdf, código, etc.)."""
    raw = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".pdf"):
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(raw))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"No se pudo leer el PDF: {exc}") from exc
    else:
        # Texto / markdown / código: decodificar como UTF-8 (con fallback).
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="replace")

    return {"filename": file.filename, "chars": len(text), "text": text}

