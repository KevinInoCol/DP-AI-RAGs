"""
Pipeline de INGESTA RAG (PDF → … → Qdrant).

Estructura:

  pipeline/
    orchestrator.py        · encadena las etapas y emite eventos de progreso (SSE)
    flow.py                · describe el flujo y sus opciones (GET /pipeline)
    stages/                · etapas puras, en orden (prefijo a_ … f_)
      a_extraction_validator.py  · clasifica cada página: texto nativo u OCR
      b_ocr.py                   · OCR de esas páginas (Tesseract o LlamaParse)
      c_normalize.py             · Unicode, des-hifenización, espacios
      d_boilerplate.py           · quita encabezados/pies repetidos
      e_chunking.py              · chunking consciente de estructura (Markdown)
      f_metadata.py              · checksum + IDs deterministas (idempotencia)
    sources/               · de dónde llegan los PDFs
      gcs.py                     · Google Cloud Storage
      onedrive.py                · OneDrive / SharePoint (Microsoft Graph)
    sink/                  · a dónde van los vectores
      naming.py                  · nombre de colección por tenant
      qdrant.py                  · crear colección, upsert, ruta de indexación

Flujo (cada página va por UNA sola rama):
  a validar ─┬─ texto nativo → loader (PyMuPDF4LLM, sin OCR) ─┬─ c normalizar
             └─ escaneada    → b OCR (Tesseract / LlamaParse) ─┘
    → d boilerplate → e chunking + f metadata → embeddings → Qdrant
"""
