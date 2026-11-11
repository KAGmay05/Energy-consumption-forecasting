"""Scratch: download one Ausgrid sample file and inspect it. Not for production."""
import hashlib
import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

# URL del espejo académico verificado para Ausgrid Solar Home Data
URL = "https://pierreh.eu/downloads/Ausgrid_solar_home_data.zip"
OUT = Path("data/raw/_scratch_ausgrid_sample")

print(f"Descargando datos desde: {URL}")
resp = requests.get(URL, timeout=60)
resp.raise_for_status()
raw = resp.content
print("sha256:", hashlib.sha256(raw).hexdigest())
print("bytes:", len(raw))

OUT.parent.mkdir(parents=True, exist_ok=True)

# Si es un archivo ZIP, listamos los contenidos y leemos un CSV de muestra
if URL.lower().endswith(".zip") or raw[:2] == b"PK":
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = zf.namelist()
    print("zip entries:", len(names))
    print("first 10 entries:", names[:10])
    
    # Buscamos un archivo CSV dentro del ZIP (por ejemplo, datos de clientes o solar)
    csv_candidates = [n for n in names if n.lower().endswith(".csv")]
    if not csv_candidates:
        raise ValueError("No se encontraron archivos CSV dentro del ZIP.")
    
    csv_name = csv_candidates[0]
    print("Leyendo archivo CSV de muestra:", csv_name)
    with zf.open(csv_name) as f:
        df = pd.read_csv(f, nrows=1000) # Leer una muestra inicial para rapidez
else:
    df = pd.read_csv(io.BytesIO(raw), nrows=1000)

print("\nshape (muestra):", df.shape)
print("columns:", list(df.columns))
print("\ndtypes:\n", df.dtypes)
print("\nhead:\n", df.head())
print("\ntail:\n", df.tail())