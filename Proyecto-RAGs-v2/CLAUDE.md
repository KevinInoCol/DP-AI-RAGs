# Proyecto-RAGs-v2 · RAG Toolkit

Banco de pruebas de RAG (loaders, splitters, embeddings, vector stores) más un
pipeline de ingesta de PDFs a Qdrant. Backend FastAPI + LlamaIndex (los splitters
también traen LangChain para comparar), frontend
React + Vite + shadcn/ui. Es la versión con la que se trabaja: la v1
(`Proyecto-RAGs`) se retiró del repo y no hay que buscarla ni restaurarla.

## Estructura

```
Backend-RAGs/
  main.py            API FastAPI (todos los endpoints)
  loaders.py         catálogo de Document Loaders (incluye LlamaParse v2, 4 tiers)
  splitters/         Text Splitters separados por framework (no mezclarlos)
    llamaindex.py    Node Parsers de LlamaIndex (claves sin prefijo)
    langchain.py     Text Splitters de LangChain (claves `lc_*`)
    common.py        count_tokens, formato de chunk, precios del semántico
    __init__.py      une los catálogos: list_splitters / split_text por `framework`
  embeddings.py      catálogo Gemini/OpenAI + resolución por API key + índice en memoria
  vectorstores.py    benchmark fuerza bruta vs. HNSW
  pipeline/
    orchestrator.py  ingesta: validar → texto nativo | OCR → normalizar → boilerplate → chunk → embed → Qdrant
    flow.py          describe el pipeline para la pestaña "Pipeline de ingesta"
    stages/          a_extraction_validator, b_ocr, c_normalize, d_boilerplate, e_chunking, f_metadata
    sources/         gcs.py (bucket GCS), onedrive.py (Microsoft Graph)
    sink/            qdrant.py (colección, upsert, chequeo de dimensión), naming.py
  tests/             pytest (d_boilerplate y splitters sin API key)
Frontend-RAGs/       React; el proxy de Vite apunta al backend en el puerto 8005
```

## Ejecutar

```bash
# Backend (Python 3.12; evitar 3.14 por falta de wheels)
cd Backend-RAGs
pip install -r requirements.txt          # tests: pip install -r requirements-dev.txt
uvicorn main:app --reload --port 8005    # el puerto 8005 es obligatorio (proxy de Vite)
pytest

# Frontend
cd Frontend-RAGs
npm install
npm run dev
```

El README menciona un entorno conda `RAG-Pipeline`, pero no existe en esta
máquina: hay que crearlo (o usar otro entorno con Python 3.12).

## Embeddings: Google u OpenAI

- Dos proveedores en `embeddings.py`: `gemini` (`gemini-embedding-2`, 768/1536/3072,
  asimétrico, `GOOGLE_API_KEY`) y `openai` (`text-embedding-3-small`, 512/1024/1536,
  simétrico, `OPENAI_API_KEY`).
- `resolve_embedder(None)` elige por la API key disponible siguiendo
  `PROVIDER_PRIORITY`. Si están ambas, gana Gemini, porque las colecciones de Qdrant
  ya ingestadas son Gemini/768.
- Pedir un proveedor explícito sin su clave debe fallar con un error claro. Nunca
  cambiar de modelo en silencio.
- El campo `embedder` es opcional en `/embed`, `/index`, `/vectorstores/benchmark`,
  `/ingest` e `/ingest/gcs`. `GET /health` informa las claves cargadas y el default.
- Los espacios vectoriales de modelos o dimensiones distintos no son compatibles.
  La ingesta comprueba el choque de dimensión con la colección existente ANTES de
  hacer OCR/embeddings (`orchestrator.ingest_documents` + `sink/qdrant.py`).
- Precios y modelos viven solo en `embeddings.py`. `splitters/common.py` y `flow.py`
  los leen del catálogo: no duplicarlos.

## Splitters: LlamaIndex vs. LangChain

- Cada framework tiene su módulo en `splitters/` y no importa al otro. Una técnica
  nueva va en el módulo de su framework; las de LangChain llevan prefijo `lc_`.
- En LangChain `chunk_size` es en caracteres (salvo `lc_token` y el recursivo en
  modo tokens). En LlamaIndex es en tokens.
- `lc_semantic` (SemanticChunker) usa `langchain-experimental` ("sunset") y
  recibe el embedder de `embeddings.py` mediante `_EmbeddingsAdapter`; no se
  añadieron `langchain-google-genai` ni `langchain-openai`.
- El diagrama del pipeline (`flow.py`) lista ambos frameworks en grupos separados
  (`option_groups`), pero la ingesta real solo usa LlamaIndex.

## Convenciones

- Colecciones de Qdrant con prefijo `tenant_id_` (skill `rag-tenant-collection-naming`;
  validación en `pipeline/sink/naming.py`).
- Orden de cabecera de los módulos Python según la skill `python-module-structure`.
- Código, comentarios, UI y mensajes de error en español.
- No dejar referencias a la empresa, plataformas internas ni personas en el código
  ni en la documentación (este proyecto es del curso de DataPath).

## Pendientes conocidos

- Falta `OPENAI_API_KEY` en `Backend-RAGs/.env` para usar OpenAI.
- El soporte de OpenAI se probó con modelos simulados, no contra las APIs reales.
- La UI no tiene pantalla de ingesta: para ingestar se llama a `/ingest` por API.
- Sin versiones fijadas: `requirements.txt` usa rangos. Se evaluó migrar a uv
  (`pyproject.toml` + `uv.lock`), pero no se ha hecho.
