"""
Descripción del pipeline de ingesta para la pestaña "Pipeline de ingesta": el flujo
de arriba hacia abajo con las opciones, el precio y el estado de cada etapa.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from pipeline.etapas.e03_ocr import list_ocr_engines
from pipeline.flujo import describe_pipeline

router = APIRouter(tags=["pipeline"])


@router.get("/ocr-engines")
def get_ocr_engines() -> dict[str, Any]:
    """Motores de OCR para las páginas escaneadas (del más barato al más caro)."""
    return {"ocr_engines": list_ocr_engines()}


@router.get("/pipeline")
def get_pipeline() -> dict[str, Any]:
    """Flujo de ingesta de arriba hacia abajo, con las opciones de cada etapa."""
    return describe_pipeline()

