# DP-AI-RAGs — Módulo 3, Sesión 2

Proyectos de RAG con bases de datos vectoriales del programa AI Engineer de DataPath.

| Carpeta | Qué hace | Vector store |
|---|---|---|
| `RAG-Servidor-Qdrant` | Servidor Qdrant compartido (docker-compose) | — |
| `RAG-con-Qdrant-para-Textos-Amazon` | Búsqueda semántica sobre nombres de producto | Qdrant, colección `tenant_id_amazon_text` |
| `RAG-con-Qdrant-para-Imagenes` | Búsqueda por texto o por imagen con CLIP | Qdrant, colección `tenant_id_amazon_images` |
| `RAG-con-Pinecone` | RAG básico sobre PDF con LangChain | Pinecone |

Las colecciones de Qdrant siguen la convención `tenant_id_<nombre>`.

## Puesta en marcha

**1. Claves.** Cada proyecto que las necesita trae un `.env.example`; cópialo a `.env` y rellénalo:

```bash
cp RAG-con-Qdrant-para-Textos-Amazon/.env.example RAG-con-Qdrant-para-Textos-Amazon/.env
cp RAG-con-Pinecone/.env.example RAG-con-Pinecone/.env
```

Los `.env` están en `.gitignore` y no deben subirse nunca.

**2. Servidor Qdrant.** Un solo contenedor sirve a los dos proyectos de Qdrant:

```bash
cd RAG-Servidor-Qdrant && docker compose up -d
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
