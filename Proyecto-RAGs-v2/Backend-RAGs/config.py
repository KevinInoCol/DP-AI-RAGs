"""
Configuración del backend: TODAS las variables de entorno en un solo lugar.

Ningún otro módulo llama a os.getenv(): importan de aquí. Así, para saber qué
necesita el sistema para funcionar, basta con leer este archivo (y .env.example).

Ninguna variable es obligatoria para arrancar la API: cada una habilita una
función concreta, y quien la usa falla con un mensaje claro si falta.

GCS no aparece aquí a propósito: google-cloud-storage lee sus credenciales solo
(ADC: `gcloud auth application-default login` o GOOGLE_APPLICATION_CREDENTIALS).
La GOOGLE_API_KEY de Gemini NO sirve para GCS.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# Embeddings (componentes/embeddings) · basta con una de las dos
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")        # gemini-embedding-2
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")        # text-embedding-3-small

# Qdrant (componentes/vectorstores · pipeline/etapas/e09_indexado)
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# LlamaParse v2: loaders de la nube y motores de OCR de pago
LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")

# SmartPDFLoader: servicio nlm-ingestor self-hosted (Docker)
LLMSHERPA_API_URL = os.getenv("LLMSHERPA_API_URL")

# OCR con Tesseract: carpeta tessdata (opcional; si falta, se busca en rutas típicas)
TESSDATA_PREFIX = os.getenv("TESSDATA_PREFIX")

# OneDrive (scripts/onedrive_test.py): Application (client) ID de Entra ID
GRAPH_CLIENT_ID = os.getenv("GRAPH_CLIENT_ID")


def variable(nombre: str) -> str | None:
    """Valor de una variable de esta configuración por su NOMBRE.

    Para los catálogos que guardan qué variable necesita cada opción (p. ej. el
    `requires_env` de cada embedder) y la consultan sin un if por proveedor.
    """
    return globals().get(nombre) if nombre.isupper() else None
