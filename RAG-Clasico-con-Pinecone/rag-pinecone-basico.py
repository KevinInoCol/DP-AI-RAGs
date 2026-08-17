import os

# Paso 1: Elección de la Técnica de DocumentLoader
from langchain_community.document_loaders import PyPDFLoader

# Paso 2: Elección de Técnica de Splitting
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Paso 3: Elección del Modelo de Word Embedding
from langchain_openai import OpenAIEmbeddings

from dotenv import load_dotenv
load_dotenv()

# Importaciones para trabajar con Pinecone
from langchain_pinecone import PineconeVectorStore

from validacion_nombre_tenant_id import validar_pinecone


if __name__ == '__main__':
    #=================================== Paso 1: Document Loader =======================================
    path = "Base_de_Conocimientos/SOBRE DATAPATH.pdf"
    loader = PyPDFLoader(path)
    documentos = loader.load()

    #======================================= Paso 2: Chunking ===========================================
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=200,
    )
    chunks = text_splitter.split_documents(documents=documentos)

    #========== Paso 3: Embeddings - Cargamos el Modelo de Embeddings para convertir los Chunks ==========
    embedding_model = OpenAIEmbeddings(model='text-embedding-ada-002')

    #======================= Paso 4: VectorStore - Llevamos los Embeddings a Pinecone ====================
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX_NAME", "tenant-id-asistente-de-ventas")

    # Falla antes de llamar a la API si el nombre no es legal para Pinecone
    # o no sigue la convención tenant-id-
    _validacion = validar_pinecone(index_name)
    if not _validacion.ok:
        raise ValueError(f"Nombre de índice inválido: {_validacion.motivos}")

    vectorstore = PineconeVectorStore.from_documents(
        documents=chunks,
        embedding=embedding_model,
        index_name=index_name,
    )

    print(f"✓ Documentos indexados correctamente en Pinecone (índice: {index_name})")
