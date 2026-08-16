import os
import requests
import pandas as pd
import numpy as np
import concurrent.futures

from typing import Optional
from zipfile import ZipFile


def download_file(url:str, directory:str) -> Optional[str]:
    # Create the directory if it doesn't exist
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Get the filename from the URL
    local_filename = os.path.join(directory, url.split('/')[-1])

    # Skip download if the file already exists (similar to `wget -nc`)
    if not os.path.exists(local_filename):
        print(f"Downloading {url}...")
        response = requests.get(url, stream=True)
        with open(local_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        print(f"Downloaded {local_filename}")
    else:
        print(f"File {local_filename} already exists, skipping download.")
    
    return local_filename

def unzip_file(zip_filepath:str, extract_to:str) -> None:
    # Extract files only if the zip file exists
    if os.path.exists(zip_filepath):
        with ZipFile(zip_filepath, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        print(f"Unzipped {zip_filepath} to {extract_to}")
    else:
        print(f"File {zip_filepath} does not exist, skipping extraction.")

def read_dataframe(path:str, dataset_fraction:float) -> pd.DataFrame:
    dataset_df = pd.read_csv(path).sample(frac=dataset_fraction)
    dataset_df["Image"] = dataset_df["Image"].map(lambda x: x.split("|")[:-1])
    dataset_df = dataset_df.explode("Image").dropna(subset=["Image"])
    return dataset_df

def download_image(url: str) -> Optional[str]:
    basename = os.path.basename(url)
    target_path = f"./data/images/{basename}"
    
    if not os.path.exists(target_path):
        try:
            # Verificar si la URL es válida antes de descargar
            response = requests.head(url)
            if response.status_code != 200:
                print(f"Skipping {url}: Status Code {response.status_code}")
                return None

            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(target_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
                        
        except requests.exceptions.RequestException as e:
            print(f"Error downloading file: {e}")
            return None
    
    return target_path


def parallel_apply_download_image(df: pd.DataFrame, column_name: str, num_workers: int = 8) -> pd.Series:
    print(f"Downloading images...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        results = list(executor.map(download_image, df[column_name].astype(str)))
    return pd.Series(results, index=df.index)


# Downloading files
i_zip_file_path = download_file("https://storage.googleapis.com/qdrant-examples/amazon-product-dataset-2020.zip", "data/")
q_zip_file_path = download_file("https://storage.googleapis.com/qdrant-examples/ecommerce-reverse-image-search-queries.zip", "queries/")

# Unzipping the queries zip file
current_folder = os.path.dirname(os.path.abspath(__file__))
unzip_file(i_zip_file_path, f"{current_folder}/data/images/")
unzip_file(q_zip_file_path, f"{current_folder}/queries/")

# Reading dataframe and downloading images
dataframe = read_dataframe('data/images/home/sdf/marketing_sample_for_amazon_com-ecommerce__20200101_20200131__10k_data.csv', 0.02)
dataframe['LocalImage'] = parallel_apply_download_image(dataframe, "Image")

# Overwrite dataframe with new columns
dataframe.to_csv('data/images/home/sdf/marketing_sample_for_amazon_com-ecommerce__20200101_20200131__10k_data.csv', index=False)