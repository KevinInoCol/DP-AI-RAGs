# DP-AI-RAGs — Módulo 3, Sesión 2

Proyectos de RAG con bases de datos vectoriales del programa AI Engineer de DataPath.

| Carpeta | Qué hace | Vector store |
|---|---|---|
| `RAG-Servidor-Qdrant` | Servidor Qdrant compartido (docker-compose) | — |
| `RAG-Clasico-con-Qdrant` | RAG sobre PDF contra el Qdrant del **VPS** | Qdrant remoto, colección `tenant_id_datapath` |
| `RAG-Clasico-con-Pinecone` | RAG básico sobre PDF con LangChain | Pinecone, índice `tenant-id-asistente-de-ventas` |
| `RAG-con-Qdrant-para-Textos-Amazon` | Búsqueda semántica sobre nombres de producto | Qdrant local, colección `tenant_id_amazon_text` |
| `RAG-con-Qdrant-para-Imagenes` | Búsqueda por texto o por imagen con CLIP | Qdrant local, colección `tenant_id_amazon_images` |

`RAG-Clasico-con-Qdrant` es el único que **no** usa el contenedor local: apunta al
Qdrant del VPS vía `QDRANT_URL` y `QDRANT_API_KEY`. Los dos proyectos de Amazon
usan `RAG-Servidor-Qdrant`.

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

Las cuatro copias son idénticas: si cambias una, replica el cambio en las otras tres.

## Puesta en marcha

**1. Claves.** Cada proyecto que las necesita trae un `.env.example`; cópialo a `.env` y rellénalo:

```bash
cp RAG-Clasico-con-Qdrant/.env.example RAG-Clasico-con-Qdrant/.env
cp RAG-Clasico-con-Pinecone/.env.example RAG-Clasico-con-Pinecone/.env
cp RAG-con-Qdrant-para-Textos-Amazon/.env.example RAG-con-Qdrant-para-Textos-Amazon/.env
```

Los `.env` están en `.gitignore` y no deben subirse nunca.

**2. Servidor Qdrant.** Un solo contenedor sirve a los dos proyectos de Amazon:

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
