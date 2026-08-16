import pandas as pd
import numpy as np
import llm #pip install llm
from PIL import Image

from typing import List, Optional
import concurrent.futures

# Assuming `llm` is already initialized or imported somewhere in your actual code
model = llm.get_embedding_model("clip") #llm install llm-clip
#El abstrae con 512 características

def read_dataframe(path: str) -> pd.DataFrame:
    dataset_df = pd.read_csv(path)
    return dataset_df

def calculate_embedding(image_path: str) -> Optional[List[float]]:
    try:
        with open(image_path, "rb") as image_file:
            embedding = model.embed(image_file.read())
        return embedding
    except Exception as e:
        print(f"Error calculating embedding for {image_path}: {e}")
        return None

def parallel_apply_calculate_embedding(df: pd.DataFrame, column_name: str, num_workers: int = 1) -> pd.Series:
    print("Calculating Embeddings")
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor: #Vamos a paralelizar este proceso con ThreadPoolExecutor
        results = list(executor.map(calculate_embedding, df[column_name].astype(str)))
    return pd.Series(results)

# Load the dataset and clean the data
dataset_df = read_dataframe('data/images/home/sdf/marketing_sample_for_amazon_com-ecommerce__20200101_20200131__10k_data.csv')
#dataset_df = dataset_df.dropna(subset=["LocalImage"])

# Apply embedding calculations in parallel and save the results
dataset_df["Embedding"] = parallel_apply_calculate_embedding(dataset_df, "LocalImage").replace({None: np.nan})
dataset_df = dataset_df.dropna(subset=["Embedding"])

# Save the resulting dataset with embeddings to a parquet file
dataset_df.to_parquet("./data/amazon-with-embeddings.parquet")


#Modelo de Embedding CLIP de OpenAI