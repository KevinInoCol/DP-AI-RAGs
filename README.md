# DP-AI-RAGs — Módulo 3, Sesión 2

Proyectos de RAG con bases de datos vectoriales del programa AI Engineer de DataPath.

Repositorio: https://github.com/KevinInoCol/DP-AI-RAGs

| Carpeta | Qué hace | Vector store |
|---|---|---|
| `RAG-Servidor-Qdrant-Local` | Servidor Qdrant compartido (docker-compose) | — |
| `Proyecto-RAGs-v2` | **RAG Toolkit**: app web (FastAPI + React) para comparar loaders, splitters de LlamaIndex y LangChain, embeddings y vector stores, más un pipeline de ingesta de PDFs | Qdrant (pipeline) y NumPy/Qdrant (benchmark) |
| `RAG-Clasico-con-Qdrant-Datapath` | RAG sobre PDF contra el Qdrant del **VPS** | Qdrant remoto, colección `tenant_id_datapath` |
| `RAG-Clasico-con-Qdrant-Municipio` | El mismo pipeline sobre el Manual de Trámites de Girardota | Qdrant remoto, colección `tenant_id_municipio_girardota` |
| `RAG-Clasico-con-Pinecone` | RAG básico sobre PDF con LangChain | Pinecone, índice `tenant-id-asistente-de-ventas` |
| `RAG-con-Qdrant-para-Textos-Amazon` | Búsqueda semántica sobre nombres de producto | Qdrant local, colección `tenant_id_amazon_text` |
| `RAG-con-Qdrant-para-Imagenes` | Búsqueda por texto o por imagen con CLIP | Qdrant local, colección `tenant_id_amazon_images` |

Los dos RAG clásicos con Qdrant (`-Datapath` y `-Municipio`) **no** usan el
contenedor local: apuntan al Qdrant del VPS vía `QDRANT_URL` y `QDRANT_API_KEY`.
Los dos proyectos de Amazon usan `RAG-Servidor-Qdrant-Local`.

## Proyecto-RAGs-v2 · RAG Toolkit

Banco de pruebas para ver cada etapa de un RAG por separado:

- **Document Loaders**: de PyPDF a LlamaParse, ordenados por calidad.
- **Text Splitters**: las técnicas de **LlamaIndex** y las de **LangChain**, en
  grupos separados, para comparar los chunks de cada una con el mismo texto.
- **Embeddings**: Gemini u OpenAI, según la API key que haya en el `.env`.
- **Vector Stores**: fuerza bruta frente a HNSW.
- **Pipeline de ingesta**: el diagrama del flujo real (validación → OCR →
  normalización → limpieza → chunking → embeddings → Qdrant), con las opciones y el
  precio de cada etapa.

Cómo levantar el backend y el frontend: [`Proyecto-RAGs-v2/Comandos.md`](Proyecto-RAGs-v2/Comandos.md).

## Convención de nombres

Las colecciones de Qdrant siguen la convención `tenant_id_<nombre>`. En Pinecone
el equivalente se escribe con guiones, `tenant-id-<nombre>`, porque el nombre del
índice forma parte del hostname DNS: solo admite minúsculas alfanuméricas y `-`,
con un máximo de 45 caracteres.

Cada proyecto incluye una copia de `validacion_nombre_tenant_id.py`, que aplica
esas reglas. Los scripts de ingesta la usan como guardia y fallan antes de llamar
a la API si el nombre no cumple. También se puede ejecutar a mano:

```bash
python validacion_nombre_tenant_id.py                             # ejemplos
python validacion_nombre_tenant_id.py --qdrant tenant_id_ventas   # exit 1 si no vale
python validacion_nombre_tenant_id.py --pinecone tenant-id-ventas
```

Las cinco copias son idénticas: si cambias una, replica el cambio en las otras
cuatro. `Proyecto-RAGs-v2` aplica la misma regla en `Backend-RAGs/pipeline/sink/naming.py`.

## Puesta en marcha

**1. Claves.** Cada proyecto que las necesita trae un `.env.example`; cópialo a `.env` y rellénalo:

```bash
cp RAG-Clasico-con-Qdrant-Datapath/.env.example RAG-Clasico-con-Qdrant-Datapath/.env
cp RAG-Clasico-con-Qdrant-Municipio/.env.example RAG-Clasico-con-Qdrant-Municipio/.env
cp RAG-Clasico-con-Pinecone/.env.example RAG-Clasico-con-Pinecone/.env
cp RAG-con-Qdrant-para-Textos-Amazon/.env.example RAG-con-Qdrant-para-Textos-Amazon/.env
cp Proyecto-RAGs-v2/Backend-RAGs/.env.example Proyecto-RAGs-v2/Backend-RAGs/.env
```

Los `.env` están en `.gitignore` y no deben subirse nunca.

**2. Servidor Qdrant.** Un solo contenedor sirve a los dos proyectos de Amazon:

```bash
cd RAG-Servidor-Qdrant-Local && docker compose up -d
```

Dashboard en http://localhost:6333/dashboard

**3. Datos.** Las carpetas `data/` se suben vacías a propósito: su contenido son
descargas y artefactos generados, no código. Se reconstruyen ejecutando los scripts
de cada proyecto en orden numérico:

```bash
python 01_setup.py       # Descarga y descomprime el dataset
python 03_embeddings.py  # Genera el parquet con los embeddings (consume API de OpenAI)
python 04_ingest_qdrant.py  # Crea la colección y sube los vectores
streamlit run 05_streamlit.py
```

En `RAG-con-Qdrant-para-Imagenes` los scripts equivalentes son `03.1_embeddings.py`
y `05.1_streamlit.py`, y los embeddings se calculan localmente con CLIP.
