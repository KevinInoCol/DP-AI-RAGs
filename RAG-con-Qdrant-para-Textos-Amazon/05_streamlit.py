import streamlit as st

from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient, models

from dotenv import load_dotenv
load_dotenv()

# Streamlit config
st.set_page_config(layout="wide")
st.title("Vector DB`s - Búsqueda por texto")

st.write('Intenta con estos términos: Funko, Funkko, Airplane')

COLLECTION_NAME = "tenant_id_amazon_text" #Debe coincidir con el de 04_ingest_qdrant.py

client = QdrantClient(url="http://localhost:6333") #Apunto al servicio Docker Qdrant que está rodando localmente

# Initialize Langchain's OpenAI Embedding model
embedding_model = OpenAIEmbeddings()

termino_de_busqueda = st.text_input("Terminos para búsqueda")

if termino_de_busqueda:
    # Create embeddings for the product names
    query_embeddings = embedding_model.embed_query(termino_de_busqueda) #Hacemos un embedding de la consulta

    st.write(query_embeddings)

    search_results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embeddings, #Usamos el embedding de la consulta para la búsqueda
        limit=3, #Obtiene como máximo 3 registros
        score_threshold=0.80, #Solo se devuelven los resultados con una similitud ≥ 0.80.
        with_payload=True #Para coger los metadatos
    ).points

    for result in search_results:
        st.image(result.payload["Image"], caption=f"Score: {result.score:.4f}")
        st.write(result)

#streamlit run 05_streamlit.py