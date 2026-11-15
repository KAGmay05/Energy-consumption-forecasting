"""Preprocesamiento del archivo meteorológico ERA5 (Open-Meteo, Sídney).

Aplica los cambios definidos en notebooks/weather_exploration.ipynb:

1. load_weather: lee el parquet congelado y comprueba su huella SHA-256.
2. validate_weather: repite los controles de calidad del cuaderno.
3. convert_wind_to_ms: pasa la velocidad del viento de km/h a m/s.
4. trim_to_period: recorta ERA5 al período horario de Ausgrid en UTC.

prepare_weather encadena los cuatro pasos. 
"""
import hashlib
from pathlib import Path

import pandas as pd

# Huella registrada en docs/data/MANIFEST.md
EXPECTED_SHA256 = "63e45ef341654d177c3670d109d54d344e971859fd46b799b1b7bb0133ae0f58"

EXPECTED_COLUMNS = [
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

# Límites físicos (mínimo, máximo); None indica que no hay límite.
DOMAINS = {
    "temperature_2m": (-50, 60),
    "relative_humidity_2m": (0, 100),
    "precipitation": (0, None),
    "cloud_cover": (0, 100),
    "shortwave_radiation": (0, None),
    "direct_normal_irradiance": (0, None),
    "diffuse_radiation": (0, None),
    "wind_speed_10m": (0, None),
    "wind_speed_10m_ms": (0, None),
    "surface_pressure": (0, None),
}

# Período de Ausgrid en UTC, con cada hora etiquetada por su final:
# 1 de julio de 2010 01:00 a 1 de julio de 2013 00:00, hora local de Sídney.
AUSGRID_START_UTC = pd.Timestamp("2010-06-30 15:00", tz="UTC")
AUSGRID_END_UTC = pd.Timestamp("2013-06-30 14:00", tz="UTC")


def load_weather(path, expected_sha256=EXPECTED_SHA256):
    """Lee el parquet de ERA5 y comprueba la huella y las columnas."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")

    file_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    if file_sha256 != expected_sha256:
        raise ValueError(
            f"La huella SHA-256 de {path.name} no coincide con el manifiesto: {file_sha256}"
        )

    weather = pd.read_parquet(path)
    missing = set(EXPECTED_COLUMNS) - set(weather.columns)
    extra = set(weather.columns) - set(EXPECTED_COLUMNS)
    if missing or extra:
        raise ValueError(f"Columnas inesperadas. Faltan: {missing}. Sobran: {extra}")
    return weather


def validate_weather(weather):
    """Comprueba índice, continuidad, celdas vacías y dominios físicos.

    No modifica los datos: si algún control falla, lanza ValueError.
    """
    index = weather.index
    errors = []

    if index.tz is None or str(index.tz) != "UTC":
        errors.append(f"el índice no está en UTC (zona: {index.tz})")
    if not index.is_monotonic_increasing:
        errors.append("el índice no está ordenado")
    duplicated = int(index.duplicated().sum())
    if duplicated:
        errors.append(f"{duplicated} marcas duplicadas")
    expected = pd.date_range(index.min(), index.max(), freq="h", tz=index.tz)
    missing_hours = len(expected.difference(index))
    if missing_hours:
        errors.append(f"{missing_hours} horas ausentes")
    empty_cells = int(weather.isna().sum().sum())
    if empty_cells:
        errors.append(f"{empty_cells} celdas vacías")

    for column, (low, high) in DOMAINS.items():
        if column not in weather.columns:
            continue
        values = weather[column]
        outside = pd.Series(False, index=values.index)
        if low is not None:
            outside |= values < low
        if high is not None:
            outside |= values > high
        if outside.any():
            errors.append(f"{int(outside.sum())} valores fuera de dominio en {column}")

    if errors:
        raise ValueError("ERA5 no supera la validación: " + "; ".join(errors))
    return weather


def convert_wind_to_ms(weather):
    """Pasa wind_speed_10m de km/h a m/s y la renombra como wind_speed_10m_ms."""
    converted = weather.copy()
    converted["wind_speed_10m"] = converted["wind_speed_10m"] / 3.6
    return converted.rename(columns={"wind_speed_10m": "wind_speed_10m_ms"})


def trim_to_period(weather, start_utc=AUSGRID_START_UTC, end_utc=AUSGRID_END_UTC):
    """Conserva solo las horas entre start_utc y end_utc, ambas incluidas."""
    trimmed = weather.loc[start_utc:end_utc]
    if trimmed.empty:
        raise ValueError("El recorte deja ERA5 sin filas; revisar el período.")
    return trimmed


def prepare_weather(path, start_utc=AUSGRID_START_UTC, end_utc=AUSGRID_END_UTC):
    """Aplica los cuatro pasos y devuelve ERA5 listo para unir con Ausgrid."""
    weather = load_weather(path)
    validate_weather(weather)
    weather = convert_wind_to_ms(weather)
    weather = trim_to_period(weather, start_utc, end_utc)
    return validate_weather(weather)


if __name__ == "__main__":
    # Ejecutar como módulo guarda el resultado: python -m src.preprocessing.weather
    project_root = Path(__file__).resolve().parents[2]
    output_path = project_root / "data" / "processed" / "era5_processed.parquet"
    weather = prepare_weather(project_root / "data" / "weather" / "era5_sydney_2010_2013.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    weather.to_parquet(output_path)
    print(f"Guardado: {output_path} ({len(weather):,} filas, {weather.shape[1]} columnas)")
