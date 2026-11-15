"""Unión de Ausgrid (horario, UTC) con ERA5 en un único conjunto.

Usa los archivos que generan ausgrid.py y weather.py:

    data/processed/ausgrid_processed.parquet
    data/processed/era5_processed.parquet

y guarda el resultado en data/processed/ausgrid_era5_joined.parquet. Ejecutar como módulo:

    python -m src.preprocessing.merge
"""
from pathlib import Path

import pandas as pd

WEATHER_COLUMNS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "cloud_cover",
    "shortwave_radiation",
    "direct_normal_irradiance",
    "diffuse_radiation",
    "wind_speed_10m_ms",
    "surface_pressure",
]


def merge_ausgrid_weather(ausgrid_hourly, weather):
    """Une Ausgrid con ERA5 por la marca UTC del final de cada hora.

    Unión izquierda muchos a uno: muchos clientes por cada hora de ERA5. Las horas de Ausgrid sin
    dato meteorológico (las 9 primeras, del 1 de julio de 2010 de 00:00 a 09:00 hora local) se
    eliminan. Comprueba que las filas solo cambien por esas horas y que no queden celdas
    meteorológicas vacías.
    """
    missing_columns = set(WEATHER_COLUMNS) - set(weather.columns)
    if missing_columns:
        raise ValueError(f"Faltan columnas de ERA5: {missing_columns}")

    weather = weather[WEATHER_COLUMNS].rename_axis("timestamp_utc").reset_index()
    if weather["timestamp_utc"].duplicated().any():
        raise ValueError("ERA5 tiene marcas UTC repetidas")

    has_weather = ausgrid_hourly["timestamp_utc"].isin(weather["timestamp_utc"])
    removed_rows = int((~has_weather).sum())
    removed_hours = ausgrid_hourly.loc[~has_weather, "timestamp_utc"].drop_duplicates().sort_values()

    merged = ausgrid_hourly.loc[has_weather].merge(
        weather, on="timestamp_utc", how="left", validate="many_to_one"
    )

    if len(merged) != len(ausgrid_hourly) - removed_rows:
        raise ValueError("La unión cambió el número de filas")
    empty_cells = int(merged[WEATHER_COLUMNS].isna().sum().sum())
    if empty_cells:
        raise ValueError(f"Quedaron {empty_cells} celdas meteorológicas vacías después de la unión")
    if merged.duplicated(["customer", "timestamp_utc"]).any():
        raise ValueError("Claves cliente + marca UTC repetidas después de la unión")

    print(f"Horas sin dato de ERA5 eliminadas: {len(removed_hours)} "
          f"({removed_rows:,} filas), de {removed_hours.min()} a {removed_hours.max()}")
    return merged.sort_values(["customer", "timestamp_utc"], ignore_index=True)


if __name__ == "__main__":
    processed = Path(__file__).resolve().parents[2] / "data" / "processed"
    ausgrid_path = processed / "ausgrid_processed.parquet"
    weather_path = processed / "era5_processed.parquet"
    for path, module in ((ausgrid_path, "ausgrid"), (weather_path, "weather")):
        if not path.is_file():
            raise FileNotFoundError(f"No existe {path}. Ejecutar antes: python -m src.preprocessing.{module}")

    merged = merge_ausgrid_weather(pd.read_parquet(ausgrid_path), pd.read_parquet(weather_path))
    output_path = processed / "ausgrid_era5_joined.parquet"
    merged.to_parquet(output_path, index=False)
    print(f"Guardado: {output_path} ({len(merged):,} filas, {merged.shape[1]} columnas)")
