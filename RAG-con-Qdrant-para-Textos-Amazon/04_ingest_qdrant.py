import pandas as pd
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

from validacion_nombre_tenant_id import validar_qdrant

client = QdrantClient("localhost")
collections = client.get_collections()
print(collections)

collection_name = "tenant_id_amazon_text" #Nombre de la coleccion (prefijo tenant_id_ por convención multi-tenant)

# Falla antes de tocar Qdrant si el nombre no cumple la convención
_validacion = validar_qdrant(collection_name)
if not _validacion.ok:
    raise ValueError(f"Nombre de colección inválido: {_validacion.motivos}")

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