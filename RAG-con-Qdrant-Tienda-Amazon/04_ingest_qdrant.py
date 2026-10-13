import os
import uuid

import pandas as pd
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from dotenv import load_dotenv

from validacion_nombre_tenant_id import validar_qdrant

load_dotenv()

# Qdrant del VPS (ya no el docker-compose local)
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
collection_name = os.getenv("QDRANT_COLLECTION") #Nombre de la coleccion (prefijo tenant_id_ por convención multi-tenant)

if not QDRANT_URL:
    raise ValueError("Falta QDRANT_URL en el .env (URL del Qdrant del VPS).")
if not collection_name:
    raise ValueError("Falta QDRANT_COLLECTION en el .env.")

# Falla antes de tocar Qdrant si el nombre no cumple la convención
_validacion = validar_qdrant(collection_name)
if not _validacion.ok:
    raise ValueError(f"Nombre de colección inválido: {_validacion.motivos}")

# port=None: sin él, qdrant-client le añade :6333 a la URL https del VPS y no conecta
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, port=None)
collections = client.get_collections()
print(collections)

# Si la colección ya existe la eliminamos antes de volver a crearla,
# así el script se puede ejecutar varias veces sin el error 409 (Conflict).
if client.collection_exists(collection_name):
    client.delete_collection(collection_name)

client.create_collection(
    collection_name=collection_name,
    vectors_config=rest.VectorParams(
        size=1536, #Cada vector tiene 1536 dimensiones
        distance=rest.Distance.COSINE, #Se usará la distancia del Coseno para medir la similitud entre vectores
    )
)

file_path = './data/images/home/sdf/amazon_product_embeddings.parquet' #Él contiene nuestras representaciones vectoriales de los productos
dataset_df = pd.read_parquet(file_path)

payloads = (
  dataset_df[["Uniq Id", "Product Name", "Product Description", "Image"]] #Seleccionamos las columnas relevantes
    .fillna("Unknown") #Reemplazamos los valores nulos (NaN) por "Unknown"
    .rename(columns={"Uniq Id": "ID", #Se renombra "Uniq Id" por "ID"
                     "Product Name": "Name", #Se renombra "Product Name" por "Name"
                     "Product Description": "Description"}) #Se renombra "Product Description" por "Description"
    .to_dict("records")
) #Se convierte el DataFrame en una lista de diccionarios (payloads).

client.upload_collection(
    collection_name=collection_name,
    vectors=list(map(list, dataset_df["embeddings"].tolist())), # Convierte embeddings en listas
    payload=payloads, #Agrega los metadatos de los productos
    ids=[uuid.uuid4().hex for _ in payloads], # Genera un ID único para cada entrada
)

# Quantidade de Registros
print(client.count(collection_name))