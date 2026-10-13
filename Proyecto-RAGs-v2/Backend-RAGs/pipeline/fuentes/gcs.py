"""
Pipeline de ingesta RAG · 01 · FUENTE Google Cloud Storage (GCS)
Ruta: Backend-RAGs/pipeline/fuentes/gcs.py

Lista y descarga PDFs de un bucket de GCS. Alimenta el mismo orquestador (pipeline/orquestador.py).

Auth: credenciales de GCP (ADC). NO usa la GOOGLE_API_KEY de Gemini — esa es de la
API de Gemini, no de GCS. Opciones:
  - Service account:  export GOOGLE_APPLICATION_CREDENTIALS=/ruta/key.json
  - Dev local:        gcloud auth application-default login
  - En Cloud Run:     la SA del servicio (Workload Identity) · sin key
Permiso mínimo sobre el bucket: roles/storage.objectViewer.
"""

from __future__ import annotations

from typing import Any


def _client():
    """Cliente de GCS con ADC. Error claro si faltan credenciales."""
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError(
            "Falta google-cloud-storage. Instálalo con: pip install google-cloud-storage"
        ) from exc
    try:
        return storage.Client()
    except Exception as exc:  # noqa: BLE001 · típicamente DefaultCredentialsError
        raise RuntimeError(
            "No hay credenciales de GCP. Configura una service account "
            "(GOOGLE_APPLICATION_CREDENTIALS=/ruta/key.json) o corre "
            "'gcloud auth application-default login'."
        ) from exc


def list_pdfs(bucket: str, prefix: str = "") -> list[dict[str, Any]]:
    """Lista los PDFs del bucket bajo `prefix`. Devuelve [{name, size, md5, updated}].
    `md5`/`updated` sirven para la sincronización incremental (saltar no cambiados)."""
    client = _client()
    out: list[dict[str, Any]] = []
    for blob in client.list_blobs(bucket, prefix=prefix or None):
        if blob.name.lower().endswith(".pdf"):
            out.append(
                {
                    "name": blob.name,
                    "size": blob.size or 0,
                    "md5": blob.md5_hash,
                    "updated": str(blob.updated) if blob.updated else None,
                }
            )
    return out


def explain_error(exc: Exception, bucket: str) -> str:
    """Mensaje accionable para los errores típicos de GCS (permiso, bucket inexistente)."""
    try:
        from google.api_core import exceptions as gexc
    except ImportError:
        return str(exc)
    if isinstance(exc, gexc.Forbidden):
        return (
            f"Sin permiso para leer gs://{bucket}. La cuenta de las credenciales de GCP "
            "necesita roles/storage.objectViewer sobre ese bucket."
        )
    if isinstance(exc, gexc.NotFound):
        return f"No existe el bucket gs://{bucket} (revisa el nombre, sin 'gs://')."
    return str(exc)


def download(bucket: str, name: str) -> bytes:
    """Descarga el contenido de un blob del bucket."""
    client = _client()
    return client.bucket(bucket).blob(name).download_as_bytes()
