# RAG - Servidor Qdrant

Servidor Qdrant compartido por los proyectos de este módulo:

- `RAG-con-Qdrant-para-Textos-Amazon` → colección `tenant_id_amazon_text` (1536 dims, embeddings de OpenAI)
- `RAG-con-Qdrant-para-Imagenes` → colección `tenant_id_amazon_images` (512 dims, embeddings de CLIP)

Un solo contenedor aloja ambas colecciones; no hace falta levantar uno por proyecto.

## Uso

```bash
docker compose up -d     # Levantar
docker compose down      # Apagar (los datos se conservan en el volumen)
docker compose logs -f   # Ver logs
```

- API REST y dashboard: http://localhost:6333/dashboard
- Los scripts de los proyectos apuntan a `http://localhost:6333`.

## Datos

La persistencia usa el volumen Docker `rag-qdrant_qdrant_storage`. El `name: rag-qdrant`
del compose fija el prefijo, de modo que renombrar o mover esta carpeta no deja
el volumen huérfano.

Para borrar los datos y empezar de cero:

```bash
docker compose down -v
```

Después de eso hay que volver a correr el `04_ingest_qdrant.py` de cada proyecto.
