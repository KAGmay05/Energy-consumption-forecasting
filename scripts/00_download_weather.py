"""Download ERA5 historical weather for Sydney, 2010-07-01 to 2013-06-30.

Reproducibility: this script documents how the frozen parquet in
data/weather/era5_sydney_2010_2013.parquet was generated. The frozen file
(SHA-256 in docs/data/MANIFEST.md) is the ground truth; re-running this
script may return slightly different values if Open-Meteo updates its ERA5
processing. Do not overwrite the frozen file.
"""
import hashlib
from pathlib import Path

import pandas as pd
import requests

URL = "https://archive-api.open-meteo.com/v1/archive"
LAT, LON = -33.8688, 151.2093  # Sydney CBD
START, END = "2010-07-01", "2013-06-30"
VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "cloud_cover",
    "shortwave_radiation",
    "direct_normal_irradiance",
    "diffuse_radiation",
    "wind_speed_10m",
    "surface_pressure",
]
OUT = Path("data/weather/era5_sydney_2010_2013.parquet")

PARAMS = {
    "latitude": LAT,
    "longitude": LON,
    "start_date": START,
    "end_date": END,
    "hourly": ",".join(VARIABLES),
    "models": "era5",
    "timezone": "UTC",
}

print(f"GET {URL}")
print(f"params: {PARAMS}")
resp = requests.get(URL, params=PARAMS, timeout=120)
resp.raise_for_status()
data = resp.json()

if "hourly" not in data:
    raise RuntimeError(f"Unexpected response: {data.get('reason', data)}")

df = pd.DataFrame(data["hourly"])
df["time"] = pd.to_datetime(df["time"], utc=True)
df = df.set_index("time").sort_index()

# Sanity checks
assert df.index.is_unique, "duplicate timestamps in response"
expected_index = pd.date_range(START, f"{END} 23:00", freq="h", tz="UTC")
missing_hours = expected_index.difference(df.index)
if len(missing_hours):
    raise RuntimeError(f"{len(missing_hours)} missing hours. First: {missing_hours[:3].tolist()}")

expected_cols = set(VARIABLES)
got_cols = set(df.columns) - {"time"}
if expected_cols != got_cols:
    print(f"WARNING: variables mismatch. Missing: {expected_cols - got_cols}, "
          f"Extra: {got_cols - expected_cols}")

null_counts = df.isna().sum()
if null_counts.any():
    print(f"WARNING: nulls per column: {null_counts[null_counts > 0].to_dict()}")

# Write
OUT.parent.mkdir(parents=True, exist_ok=True)
if OUT.exists():
    print(f"WARNING: {OUT} already exists. Overwriting. "
          f"If this was the frozen version, restore from the team share.")

df.to_parquet(OUT)
h = hashlib.sha256(OUT.read_bytes()).hexdigest()

print()
print(f"saved: {OUT}")
print(f"rows: {len(df)}")
print(f"columns: {df.columns.tolist()}")
print(f"range: {df.index.min()} -> {df.index.max()}")
print(f"sha256: {h}")
print()
print("describe:")
print(df.describe().T.to_string())