"""
Pipeline de INGESTA RAG (PDF → … → Qdrant).

Cada etapa tiene el MISMO número que su tarjeta en la pestaña "Pipeline de ingesta".

  pipeline/
    orquestador.py   · encadena las etapas y emite eventos de progreso (SSE)
    flujo.py         · describe el flujo y sus opciones para la UI (GET /pipeline)
    naming.py        · nombre de la colección de Qdrant a partir del tenant
    fuentes/         · 01 · de dónde llegan los PDFs
      gcs.py               · bucket de Google Cloud Storage
      onedrive.py          · OneDrive / SharePoint (Microsoft Graph)
    etapas/
      e02_validacion.py    · clasifica cada página: texto nativo u OCR
      e03_loader.py        · rama No: texto nativo → Markdown (PyMuPDF4LLM)
      e03_ocr.py           · rama Sí: OCR en español (Tesseract o LlamaParse)
      e04_normalizacion.py · Unicode, des-hifenización, espacios
      e05_limpieza.py      · quita encabezados/pies repetidos
      e06_chunking.py      · chunking estructural o un splitter del catálogo
      e07_metadata.py      · checksum + IDs deterministas (idempotencia)
      e08_embeddings.py    · vectores con Google u OpenAI
      e09_indexado.py      · Qdrant: crear colección, upsert, ruta de indexación

Flujo (cada página va por UNA sola rama):
  01 fuente → 02 validar ─┬─ texto nativo → 03 loader ─┬─ 04 normalizar → 05 limpieza
                          └─ escaneada    → 03 OCR    ─┘
    → 06 chunking → 07 metadata → 08 embeddings → 09 indexado (Qdrant)

Las opciones de cada etapa (loaders, splitters, embeddings, vector stores) salen de
componentes/, los mismos catálogos que compara el banco de pruebas.
"""
