"""Segmentos de evaluación (docs/modelado/decisiones.md, sección 5).

day_segments da, para cada día local, el tipo de día, la estación y si es de Navidad o de calor.
grid_segments asigna esas etiquetas, y la de casa vacía, a las horas de un ForecastGrid, en el
formato que espera metrics.evaluate.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from src.features.calendar import day_calendar, local_date

WEATHER_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "era5_processed.parquet"
HEAT_THRESHOLD_C = 30.0
YES_NO = ["no", "sí"]


def daily_max_temperature(temperature):
    """Máxima de cada día local, a partir de una Series horaria indexada por la marca UTC del final de la hora."""
    days = np.asarray(local_date(temperature.index))
    return temperature.groupby(days).max().rename_axis("fecha_local").rename("temp_max")


def load_daily_max_temperature(path=WEATHER_PATH):
    """Lee ERA5 procesado y devuelve la temperatura máxima de cada día local."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró {path}. Ejecutar antes: python -m src.preprocessing.weather")
    return daily_max_temperature(pd.read_parquet(path, columns=["temperature_2m"])["temperature_2m"])


def day_segments(dates, temperature_max):
    """Una fila por día local con los segmentos tipo_dia, estacion, navidad y calor."""
    calendar = day_calendar(dates)
    temperature = temperature_max.reindex(calendar.index)
    if temperature.isna().any():
        raise ValueError(f"Falta la temperatura máxima de {int(temperature.isna().sum())} días")
    return pd.DataFrame({
        "tipo_dia": calendar["tipo_dia"],
        "estacion": calendar["estacion"],
        "navidad": pd.Categorical(np.where(calendar["navidad"], "sí", "no"), categories=YES_NO),
        "calor": pd.Categorical(np.where(temperature >= HEAT_THRESHOLD_C, "sí", "no"), categories=YES_NO),
    }, index=calendar.index)


def grid_segments(grid, segments, vacancy=None, customers=None):
    """Etiquetas de cada segmento en las horas de un ForecastGrid.

    Devuelve un dict nombre -> (códigos, categorías). Los códigos tienen forma (orígenes, MAX_STEPS)
    y valen −1 fuera del horizonte. Si se pasa vacancy (flag_vacant_days) junto con los hogares del
    panel, se añade casa_vacia, con forma (hogares, orígenes, MAX_STEPS).
    """
    rows = segments.index.get_indexer(pd.DatetimeIndex(grid.fecha_local.ravel())).reshape(grid.fecha_local.shape)
    if (grid.in_horizon & (rows < 0)).any():
        raise ValueError("Hay días del horizonte sin segmentos")
    rows = np.where(grid.in_horizon, rows, 0)

    result = {}
    for column in segments.columns:
        codes = segments[column].cat.codes.to_numpy()[rows]
        result[column] = (np.where(grid.in_horizon, codes, -1).astype("int8"), list(segments[column].cat.categories))

    if vacancy is not None:
        if customers is None:
            raise ValueError("Para casa_vacia hacen falta los hogares del panel")
        days = (vacancy.unstack("fecha_local", fill_value=False)
                .reindex(index=customers, columns=segments.index, fill_value=False)
                .to_numpy(dtype=bool))
        codes = days[:, rows].astype("int8")
        codes[:, ~grid.in_horizon] = -1
        result["casa_vacia"] = (codes, YES_NO)
    return result
