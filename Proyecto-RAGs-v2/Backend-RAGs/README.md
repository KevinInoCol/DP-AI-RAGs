# Backend-RAGs · API de Text Splitters (FastAPI + LlamaIndex)

API que aplica los distintos **Text Splitters / Node Parsers** de LlamaIndex
sobre un texto y devuelve los chunks resultantes.

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

| Método | Ruta         | Descripción                                  |
|--------|--------------|----------------------------------------------|
| GET    | `/splitters` | Catálogo de técnicas, agrupadas por framework (LlamaIndex / LangChain) |
| POST   | `/split`     | Divide un texto con el splitter elegido      |
| POST   | `/extract`   | Extrae texto de un archivo (.txt/.md/.pdf…)  |
| GET    | `/embedders` | Modelos de embedding (Google u OpenAI)       |
| POST   | `/ingest`    | Ingesta de PDFs a Qdrant (SSE)               |
| GET    | `/health`    | Estado del servicio y claves cargadas        |

## Splitters incluidos

Están separados por framework en el paquete `splitters/`: cada catálogo vive en
su propio módulo y la UI los muestra en dos grupos.

### LlamaIndex (`splitters/llamaindex.py`)

**🟢 Sin API Key**
- `SentenceSplitter`
- `TokenTextSplitter`
- `SentenceWindowNodeParser`
- `CodeSplitter`

**🔵 Con API Key (embeddings: Google u OpenAI)**
- `SemanticSplitterNodeParser` — usa el mismo modelo que la indexación

### LangChain (`splitters/langchain.py`, claves `lc_*`)

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
