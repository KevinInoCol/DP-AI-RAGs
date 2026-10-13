# Proyecto-RAGs-v2 · RAG Toolkit

Banco de pruebas de RAG (loaders, splitters, embeddings, vector stores) más un
pipeline de ingesta de PDFs a Qdrant. Backend FastAPI + LlamaIndex (los splitters
también traen LangChain para comparar), frontend
React + Vite + shadcn/ui. Es la versión con la que se trabaja: la v1
(`Proyecto-RAGs`) se retiró del repo y no hay que buscarla ni restaurarla.

## Estructura

```
Backend-RAGs/
  main.py            solo arma la app (CORS + routers); los endpoints están en api/routers/
  config.py          TODAS las variables de entorno; ningún otro módulo llama a os.getenv
  api/
    schemas.py       modelos de las peticiones JSON
    routers/         banco.py · pipeline.py · ingesta.py · sistema.py (uno por área de la UI)
  componentes/       catálogo + implementación de cada componente (los usan banco e ingesta)
    loaders/         catalogo.py · locales.py · llamaparse.py (LlamaParse v2, 4 tiers; también lo usa el OCR)
    splitters/       separados por framework (no mezclarlos)
      llamaindex.py  Node Parsers de LlamaIndex (claves sin prefijo)
      langchain.py   Text Splitters de LangChain (claves `lc_*`)
      common.py      count_tokens, formato de chunk, precios del semántico
      __init__.py    une los catálogos: list_splitters / split_text por `framework`
    embeddings/      proveedores.py (Gemini/OpenAI + resolución por API key) · indice_memoria.py (solo banco)
    vectorstores/    qdrant.py (cliente compartido) · benchmark.py (fuerza bruta vs. HNSW, solo banco)
  pipeline/
    orquestador.py   encadena las etapas en orden; sin lógica de negocio
    flujo.py         describe el pipeline para la pestaña "Pipeline de ingesta"
    naming.py        nombre de colección por tenant
    fuentes/         01 · gcs.py (bucket GCS), onedrive.py (Microsoft Graph)
    etapas/          e02_validacion · e03_loader · e03_ocr · e04_normalizacion · e05_limpieza
                     e06_chunking · e07_metadata · e08_embeddings · e09_indexado
  scripts/           pruebas manuales (python -m scripts.onedrive_test)
  tests/             pytest (e05_limpieza y splitters sin API key)
Frontend-RAGs/       React; el proxy de Vite apunta al backend en el puerto 8005
```

Regla de la estructura: el número de cada archivo de `pipeline/etapas/` es el de su
tarjeta en la pestaña Pipeline (campo `number` de cada nodo de `flujo.py`; la UI no
numera por su cuenta), y el campo `module` apunta al archivo real.

Ruta de indexación (`etapas/e09_indexado.index_route`): la decide Qdrant solo, en
segundo plano y por segmento. Su `indexing_threshold` está en KB de vectores por
segmento (1 KB = 256 dims), NO en número de vectores. La ingesta reporta la ruta
real leyendo `indexed_vectors_count`: `brute_force`, `mixed` o `hnsw`. El servidor
del curso usa 10 000 KB (≈ 1 666 vectores de 1536 dims por segmento). Una etapa nueva lleva su número; una opción nueva de un
componente va en su catálogo de `componentes/`, no en el pipeline.

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

Entorno: conda `RAG-Pipeline` (Python 3.12) en `/opt/anaconda3/envs/RAG-Pipeline`,
con `requirements-dev.txt` instalado (pytest incluido).

## Embeddings: Google u OpenAI

- Dos proveedores en `componentes/embeddings/proveedores.py`: `gemini` (`gemini-embedding-2`, 768/1536/3072,
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
  hacer OCR/embeddings (`orquestador.ingest_documents` + `etapas/e09_indexado.check_dimension`).
- Precios y modelos viven solo en `componentes/embeddings/proveedores.py`. `splitters/common.py` y `flujo.py`
  los leen del catálogo: no duplicarlos.

## Splitters: LlamaIndex vs. LangChain

- Cada framework tiene su módulo en `splitters/` y no importa al otro. Una técnica
  nueva va en el módulo de su framework; las de LangChain llevan prefijo `lc_`.
- En LangChain `chunk_size` es en caracteres (salvo `lc_token` y el recursivo en
  modo tokens). En LlamaIndex es en tokens.
- `lc_semantic` (SemanticChunker) usa `langchain-experimental` ("sunset") y
  recibe el embedder de `componentes/embeddings` mediante `_EmbeddingsAdapter`; no se
  añadieron `langchain-google-genai` ni `langchain-openai`.
- El diagrama del pipeline (`flujo.py`) lista ambos frameworks en grupos separados
  (`option_groups`). La ingesta usa por defecto el chunking estructural
  (`INGEST_SPLITTER` en `etapas/e06_chunking.py`), pero `/ingest` acepta `splitter` con cualquier técnica de
  los dos frameworks, salvo las de `SPLITTERS_NOT_FOR_INGEST` (código, JSON, HTML).

## Pipeline interactivo

- Los nodos de `flujo.py` con `field` (`source`, `loader`, `ocr_engine`, `splitter`, `embedder`)
  son elegibles: en la pestaña Pipeline un click en una opción la selecciona, y el
  panel "Ejecutar ingesta" (`IngestPanel.jsx`) lanza la ingesta con esa selección y
  muestra el progreso SSE. La configuración se guarda SOLA en `localStorage` en cuanto
  cambia (opciones del diagrama, tenant, bucket y prefijo; los PDFs no), sin botón ni
  ingesta de por medio.
- La colección se elige en la tarjeta 09 (`CollectionInput.jsx`): prefijo `tenant_id_`
  fijo + lo que escribe el usuario. `GET /collections/preview` devuelve el nombre final
  con las reglas de `pipeline/naming.py`, si ya existe y si su dimensión choca con el
  embedder elegido; `GET /collections` lista las existentes para reutilizarlas.
- `loader` acepta solo los loaders de un documento por página (`PAGE_LOADERS` en
  `etapas/e03_loader.py`): la etapa les pasa un PDF con las páginas de texto nativo y
  reasigna cada resultado a su página. Unstructured, PDFTableReader y SmartPDFLoader
  quedan solo para comparar en su pestaña.
- `source` = `upload` llama a `/ingest` con los PDFs subidos; `gcs` llama a
  `/ingest/gcs` con bucket + prefijo (`GET /gcs/pdfs` los lista antes). GCS usa las
  credenciales ADC de GCP, no la `GOOGLE_API_KEY`; hace falta
  `roles/storage.objectViewer` sobre el bucket.

## Convenciones

- Colecciones de Qdrant con prefijo `tenant_id_` (skill `rag-tenant-collection-naming`;
  validación en `pipeline/naming.py`).
- Orden de cabecera de los módulos Python según la skill `python-module-structure`.
- Código, comentarios, UI y mensajes de error en español.
- No dejar referencias a la empresa, plataformas internas ni personas en el código
  ni en la documentación (este proyecto es del curso de DataPath).

## Pendientes conocidos

- Falta `OPENAI_API_KEY` en `Backend-RAGs/.env` para usar OpenAI.
- El soporte de OpenAI se probó con modelos simulados, no contra las APIs reales.
- El vector store de la ingesta sigue fijo (Qdrant).
- Sin versiones fijadas: `requirements.txt` usa rangos. Se evaluó migrar a uv
  (`pyproject.toml` + `uv.lock`), pero no se ha hecho.
