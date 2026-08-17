---
name: rag-tenant-collection-naming
description: Convención de nombrado multi-tenant para colecciones e índices de vector stores en proyectos RAG — prefijo `tenant_id_` en Qdrant (guiones bajos) y `tenant-id-` en Pinecone (guiones, máx. 45 caracteres). Incluye el validador que se copia a cada proyecto. Use whenever creating, renaming, or querying a vector store collection/index in a RAG project — Qdrant `create_collection`, Pinecone `create_index`, LangChain `QdrantVectorStore`/`PineconeVectorStore`, LlamaIndex vector stores, or `.env` values like `QDRANT_COLLECTION` / `PINECONE_INDEX_NAME`. Apply automatically without asking.
---

# Nombrado multi-tenant de colecciones RAG

Toda colección o índice de vector store que crees lleva el prefijo del tenant.
El motor por defecto de este usuario es **Qdrant**; Pinecone es el caso
secundario. La convención es la misma idea en los dos, pero **se escribe
distinto**, y confundirlas rompe el proyecto.

| Motor | Forma | Ejemplo |
|---|---|---|
| **Qdrant** (por defecto) | `tenant_id_<nombre>` — guiones bajos | `tenant_id_datapath` |
| **Pinecone** | `tenant-id-<nombre>` — guiones | `tenant-id-asistente-de-ventas` |

## Por qué difieren

No es capricho. **Pinecone rechaza los guiones bajos**: el nombre del índice
forma parte del hostname DNS al que apunta el cliente, así que solo admite
minúsculas alfanuméricas y `-`, debe empezar y terminar en alfanumérico, y tiene
un **máximo de 45 caracteres**. Los puntos también están prohibidos.

Qdrant es permisivo: acepta guiones bajos sin problema (su propio quickstart usa
`test_collection`) y solo rechaza caracteres que romperían la ruta HTTP o el
nombre de carpeta en disco: `< > : " / \ | ? *` y caracteres de control.

## Trampa del límite de 45

Sumar `tenant-id-` (10 caracteres) a un nombre ya largo se pasa del límite sin
que sea evidente. Cuando adaptes un nombre existente a Pinecone, **cuenta los
caracteres** y acorta la parte descriptiva, no el prefijo.

## Cómo aplicarlo

1. **Define el nombre en una sola constante** por script y reutilízala. Nunca
   repitas el literal entre el script de ingesta y el de consulta: se
   desincronizan y el error aparece como "colección vacía", no como fallo.
2. **Léelo del `.env`** cuando el proyecto tenga uno
   (`QDRANT_COLLECTION`, `PINECONE_INDEX_NAME`), con el nombre correcto como
   valor por defecto.
3. **Copia `validacion_nombre_tenant_id.py`** (está junto a este SKILL.md) a la
   raíz del proyecto nuevo, y úsalo como guardia en el script de ingesta:

```python
from validacion_nombre_tenant_id import validar_qdrant

validacion = validar_qdrant(COLLECTION_NAME)
if not validacion.ok:
    raise ValueError(f"Nombre de colección inválido: {validacion.motivos}")
```

   La guardia va con el resto de precondiciones, antes de cargar documentos o
   llamar al modelo de embeddings. Para Pinecone, `validar_pinecone`. La función
   `a_nombre_pinecone()` traduce de un dialecto al otro.

4. **El validador también corre como CLI**, con exit 1 si el nombre no vale:

```bash
python validacion_nombre_tenant_id.py --qdrant tenant_id_ventas
python validacion_nombre_tenant_id.py --pinecone tenant-id-ventas
```

## Alternativa en Pinecone: namespaces

Pinecone recomienda **un namespace por cliente** para aislar inquilinos, no un
índice por cliente. El namespace viaja en el cuerpo de la petición, no en el
DNS, así que admite guiones bajos y conserva la forma de Qdrant.

Cuando el objetivo sea modelar multi-tenancy de verdad (no solo etiquetar),
propone al usuario el namespace: el índice es infraestructura, el namespace es
el inquilino. Cuando el objetivo sea didáctico o de consistencia visual entre
proyectos, el prefijo en el nombre del índice es suficiente.

## Avisos al renombrar

Renombrar **no renombra nada** en ninguno de los dos motores: se crea una
colección/índice nuevo y el anterior sigue existiendo. Adviértelo siempre, y en
Pinecone menciona además que un índice serverless huérfano sigue generando
coste hasta que se borre a mano.
