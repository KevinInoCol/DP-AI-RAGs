# Backend-RAGs · API del RAG Toolkit (FastAPI + LlamaIndex)

API con dos mitades:

- **Banco de pruebas:** compara técnicas de cada componente de un RAG (Document
  Loaders, Text Splitters, Embeddings, Vector Stores), una pestaña por componente.
- **Pipeline de ingesta:** lleva PDFs hasta Qdrant en 9 etapas, las mismas que
  dibuja la pestaña "Pipeline de ingesta", eligiendo una opción de cada componente.

## Estructura

```
Backend-RAGs/
  main.py              arma la app: CORS + routers (no tiene endpoints propios)
  config.py            TODAS las variables de entorno, en un solo lugar
  api/
    schemas.py         modelos de las peticiones JSON
    routers/
      banco.py         /loaders /load /splitters /split /embedders /embed /index /search /vectorstores…
      pipeline.py      /pipeline /ocr-engines
      ingesta.py       /ingest /gcs/pdfs /ingest/gcs  (SSE)
      sistema.py       /health /extract
  componentes/         catálogo + implementación de cada componente (banco e ingesta)
    loaders/           catalogo.py · locales.py · llamaparse.py
    splitters/         llamaindex.py · langchain.py · common.py
    embeddings/        proveedores.py · indice_memoria.py (solo banco)
    vectorstores/      qdrant.py (cliente compartido) · benchmark.py (solo banco)
  pipeline/
    orquestador.py     encadena las etapas y emite eventos de progreso
    flujo.py           describe el flujo para la UI (GET /pipeline)
    naming.py          nombre de la colección de Qdrant por tenant
    fuentes/           01 · gcs.py · onedrive.py
    etapas/            e02_validacion · e03_loader · e03_ocr · e04_normalizacion · e05_limpieza
                       e06_chunking · e07_metadata · e08_embeddings · e09_indexado
  scripts/             pruebas manuales (onedrive_test.py: python -m scripts.onedrive_test)
  tests/               pytest
```

El número de cada etapa es el de su tarjeta en la pestaña, y el campo "módulo"
de cada tarjeta apunta a su archivo.

## Instalación (conda)

```bash
cd Backend-RAGs
conda activate RAG-Pipeline      # entorno ya creado con Python 3.12
pip install -r requirements.txt
```

> El entorno `RAG-Pipeline` usa Python 3.12. Evita las versiones muy nuevas
> (3.14) porque `tiktoken`/`tree-sitter` aún no traen wheels para ellas.

## Configuración (opcional)

Solo necesaria para los splitters **semánticos** y las etapas de indexación /
ingesta:

```bash
cp .env.example .env
# edita .env y coloca UNA (o las dos) claves de embeddings
```

### Embeddings: Google u OpenAI

Hay **dos proveedores intercambiables**. Si no se indica ninguno, el backend elige
mirando qué API key está definida en el `.env` — no hay que tocar código:

| Proveedor | Modelo                   | Variable         | Dimensiones      | Retrieval  | Precio          |
|-----------|--------------------------|------------------|------------------|------------|-----------------|
| Google    | `gemini-embedding-2`     | `GOOGLE_API_KEY` | 768/1536/3072    | asimétrico | $0.20 / 1M tok. |
| OpenAI    | `text-embedding-3-small` | `OPENAI_API_KEY` | 512/1024/1536    | simétrico  | $0.02 / 1M tok. |

- Basta **una** de las dos claves. Si están **ambas**, el default es **Google**,
  pero se puede elegir OpenAI en la UI o con el campo `embedder` (`"gemini"` |
  `"openai"`) de `/embed`, `/index`, `/vectorstores/benchmark`, `/ingest` e
  `/ingest/gcs`.
- La resolución vive en `embeddings.resolve_embedder()` y la usan el catálogo
  `/embedders`, el splitter semántico y el pipeline de ingesta.
- Pedir un proveedor explícito sin su clave **falla con un error claro**: nunca se
  cambia de modelo en silencio.
- `GET /health` reporta qué claves hay (`embedders_available`, `embedder_default`).

> ⚠️ Los espacios vectoriales de distintos modelos/dimensiones **no son
> compatibles**. Una colección de Qdrant creada con Gemini (768) no admite
> vectores de OpenAI (1536): la ingesta detecta el choque **antes** de embeber y
> lo explica, en vez de dejar que Qdrant tire un error opaco.

## Ejecutar

```bash
conda activate RAG-Pipeline
uvicorn main:app --reload --port 8005
```

Docs interactivas: http://localhost:8005/docs

## Endpoints

| Router | Método | Ruta | Descripción |
|---|---|---|---|
| banco | GET | `/loaders` | Catálogo de Document Loaders, de peor a mejor |
| banco | POST | `/load` | Extrae un archivo con el loader elegido |
| banco | GET | `/splitters` | Catálogo de técnicas, agrupadas por framework (LlamaIndex / LangChain) |
| banco | POST | `/split` | Divide un texto con el splitter elegido |
| banco | GET | `/embedders` | Modelos de embedding (Google u OpenAI) |
| banco | POST | `/embed` | Embebe textos y devuelve stats + preview de cada vector |
| banco | POST | `/index` · `/search` | Índice en memoria: indexar chunks y consultarlos |
| banco | GET | `/vectorstores` | Motores de índice (fuerza bruta vs. HNSW) |
| banco | POST | `/vectorstores/benchmark` | Compara build, búsqueda y recall@k |
| pipeline | GET | `/pipeline` | Flujo de ingesta con las opciones de cada etapa |
| pipeline | GET | `/ocr-engines` | Motores de OCR elegibles para la ingesta |
| ingesta | POST | `/ingest` | Ingesta de PDFs subidos a Qdrant (SSE): `ocr_engine`, `splitter`, `embedder` opcionales |
| ingesta | GET | `/gcs/pdfs` | Lista los PDFs de un bucket de GCS |
| ingesta | POST | `/ingest/gcs` | Ingesta de los PDFs de un bucket de GCS (SSE) |
| sistema | GET | `/health` | Estado del servicio y claves cargadas |
| sistema | POST | `/extract` | Extrae texto de un archivo (.txt/.md/.pdf…) |

## Splitters incluidos

Están separados por framework en el paquete `componentes/splitters/`: cada catálogo vive en
su propio módulo y la UI los muestra en dos grupos.

### LlamaIndex (`componentes/splitters/llamaindex.py`)

**🟢 Sin API Key**
- `SentenceSplitter`
- `TokenTextSplitter`
- `SentenceWindowNodeParser`
- `CodeSplitter`

**🔵 Con API Key (embeddings: Google u OpenAI)**
- `SemanticSplitterNodeParser` — usa el mismo modelo que la indexación

### LangChain (`componentes/splitters/langchain.py`, claves `lc_*`)

> En LangChain `chunk_size` se mide en **caracteres** (salvo `TokenTextSplitter`
> y el modo "tokens" del recursivo). En LlamaIndex se mide en tokens.

**🟢 Sin API Key**
- `RecursiveCharacterTextSplitter` — en caracteres o tokens
- `CharacterTextSplitter`
- `TokenTextSplitter` (tiktoken)
- `NLTKTextSplitter` — descarga `punkt_tab` la primera vez
- `MarkdownHeaderTextSplitter` — encabezados como metadata
- `HTMLHeaderTextSplitter` — encabezados como metadata
- `RecursiveCharacterTextSplitter.from_language` — código, Markdown, LaTeX, HTML
- `RecursiveJsonSplitter` — la entrada debe ser un objeto JSON

**🔵 Con API Key (embeddings: Google u OpenAI)**
- `SemanticChunker` (`langchain-experimental`, sin mantenimiento activo) — usa
  el mismo modelo que la indexación a través de un adaptador
