import os
import requests

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


# Downloading files
i_zip_file_path = download_file("https://storage.googleapis.com/qdrant-examples/amazon-product-dataset-2020.zip", "data/")

# Unzipping the queries zip file
current_folder = os.path.dirname(os.path.abspath(__file__))
unzip_file(i_zip_file_path, f"{current_folder}/data/images/")