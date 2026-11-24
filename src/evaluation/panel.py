"""Matrices hogar × hora para pronosticar y evaluar.

load_panel lee data/processed/ausgrid_era5_joined.parquet y coloca cada columna en una matriz con
una fila por hogar y una columna por hora UTC, en orden cronológico y sin saltos en el eje de
tiempo. Las horas que no existen en los datos, los 81 días del hogar 2 (G14), quedan como NaN, o
como False en las columnas booleanas, y present indica qué celdas tienen dato.
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "ausgrid_era5_joined.parquet"
ONE_HOUR = np.timedelta64(1, "h")


@dataclass(frozen=True)
class Panel:
    """Valores de cada hogar (filas) en cada hora (columnas).

    timestamps son las marcas UTC del final de cada hora, como timestamp_utc.
    """
    customers: np.ndarray
    timestamps: pd.DatetimeIndex
    present: np.ndarray
    values: dict

    def __getitem__(self, column):
        if column not in self.values:
            raise KeyError(f"La columna {column} no se cargó en el panel")
        return self.values[column]

    def positions(self, timestamps_utc):
        """Posición en el eje de tiempo de cada marca UTC, con la misma forma que la entrada.

        Acepta marcas con zona horaria o datetime64 sin zona, que se interpretan como UTC. Lanza
        ValueError si alguna marca no es una hora exacta del panel.
        """
        if isinstance(timestamps_utc, (pd.DatetimeIndex, pd.Series)):
            index = pd.DatetimeIndex(timestamps_utc)
            timestamps_utc = (index.tz_convert(None) if index.tz is not None else index).to_numpy()
        values = np.asarray(timestamps_utc, dtype="datetime64[ns]")
        offset = values - self.timestamps[0].tz_convert(None).to_datetime64()
        positions = (offset // ONE_HOUR).astype("int64")
        if values.size == 0:
            return positions
        if (offset % ONE_HOUR != np.timedelta64(0, "ns")).any():
            raise ValueError("Hay marcas que no caen en una hora exacta")
        if positions.min() < 0 or positions.max() >= len(self.timestamps):
            raise ValueError("Hay marcas fuera del periodo del panel")
        return positions


def build_panel(data, columns):
    """Construye el panel a partir de un conjunto largo con customer, timestamp_utc y columns."""
    if data.duplicated(["customer", "timestamp_utc"]).any():
        raise ValueError("Hay filas repetidas de hogar y hora")
    customers = np.sort(data["customer"].unique())
    timestamps = pd.date_range(data["timestamp_utc"].min(), data["timestamp_utc"].max(), freq="h")
    rows = np.searchsorted(customers, data["customer"].to_numpy())
    cols = ((data["timestamp_utc"] - timestamps[0]) // pd.Timedelta(hours=1)).to_numpy()

    shape = (len(customers), len(timestamps))
    present = np.zeros(shape, dtype=bool)
    present[rows, cols] = True
    values = {}
    for column in columns:
        source = data[column]
        matrix = np.zeros(shape, dtype=bool) if source.dtype == bool else np.full(shape, np.nan)
        matrix[rows, cols] = source.to_numpy()
        values[column] = matrix
    return Panel(customers=customers, timestamps=timestamps, present=present, values=values)


def load_panel(columns=("demand_kwh", "cl_estimated"), path=DATA_PATH):
    """Lee el conjunto final y devuelve el panel con las columnas pedidas."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró {path}. Ejecutar antes los scripts de src/preprocessing")
    columns = list(columns)
    data = pd.read_parquet(path, columns=["customer", "timestamp_utc", *columns])
    return build_panel(data, columns)
