"""Datos sintéticos compartidos por los tests. No usan los archivos de data/."""
import numpy as np
import pandas as pd
import pytest

from src.evaluation.panel import build_panel
from src.evaluation.splits import local_midnight_utc
from src.features.calendar import local_date

# Hogar 2: le falta un día entero. Hogar 1: un día con CL estimado.
GAP_DAY = pd.Timestamp("2011-12-10")
CL_ESTIMATED_DAY = pd.Timestamp("2011-08-15")


def hours_between(first_day, last_day):
    """Marcas UTC (final de la hora) de todas las horas locales de first_day a last_day, ambos incluidos."""
    start = local_midnight_utc([first_day])[0] + pd.Timedelta(hours=1)
    end = local_midnight_utc([last_day + pd.Timedelta(days=1)])[0]
    return pd.date_range(start, end, freq="h")


@pytest.fixture(scope="session")
def validation_panel():
    """Dos hogares con consumo aleatorio que cubren el pliegue de validación y sus 28 días previos."""
    stamps = hours_between(pd.Timestamp("2011-06-01"), pd.Timestamp("2012-06-30"))
    days = local_date(stamps)
    rng = np.random.default_rng(0)
    frames = []
    for customer in (1, 2):
        frame = pd.DataFrame({
            "customer": customer,
            "timestamp_utc": stamps,
            "demand_kwh": rng.gamma(2.0, 0.4, len(stamps)),
            "cl_estimated": np.asarray(days == CL_ESTIMATED_DAY) & (customer == 1),
        })
        if customer == 2:
            frame = frame.loc[np.asarray(days != GAP_DAY)]
        frames.append(frame)
    return build_panel(pd.concat(frames, ignore_index=True), ["demand_kwh", "cl_estimated"])
