"""Marca de casa vacía (docs/modelado/decisiones.md, sección 6).

Para cada hogar y día local, la hora típica es la mediana de sus horas de GC. La habitual del
hogar es la mediana de su hora típica en el periodo de referencia, los dos años de
entrenamiento. Un día se marca si su hora típica es menor que el 30 % de la habitual y forma parte
de una racha de al menos 3 días seguidos así (forecasting_eda.ipynb, sección 2.5).

La marca se calcula conociendo el consumo del propio día, así que solo sirve para evaluar o para
probar a quitar días del entrenamiento. Nunca debe usarse como variable de entrada.
"""
import numpy as np
import pandas as pd

from src.features.calendar import local_date

VACANCY_RATIO = 0.30
MIN_RUN_DAYS = 3
REFERENCE_FIRST_DAY = pd.Timestamp("2010-07-01")
REFERENCE_LAST_DAY = pd.Timestamp("2012-06-30")


def typical_hour(data):
    """Mediana de gc_kwh de cada hogar y día local.

    data necesita las columnas customer, timestamp_utc y gc_kwh. Devuelve una Series indexada
    por (customer, fecha_local).
    """
    missing = {"customer", "timestamp_utc", "gc_kwh"} - set(data.columns)
    if missing:
        raise ValueError(f"Faltan columnas: {missing}")
    days = np.asarray(local_date(data["timestamp_utc"]))
    typical = data["gc_kwh"].groupby([data["customer"].to_numpy(), days]).median()
    return typical.rename_axis(["customer", "fecha_local"]).rename("hora_tipica")


def flag_vacant_days(typical, reference_first_day=REFERENCE_FIRST_DAY, reference_last_day=REFERENCE_LAST_DAY,
                     ratio=VACANCY_RATIO, min_days=MIN_RUN_DAYS):
    """Marca los días de casa vacía a partir de la hora típica de cada hogar y día (typical_hour).

    Una racha se corta al cambiar de hogar o cuando falta un día, como en el hueco del hogar 2
    (G14): los días a cada lado del hueco no se cuentan como seguidos.
    """
    typical = typical.sort_index()
    customers = typical.index.get_level_values("customer")
    dates = typical.index.get_level_values("fecha_local")

    in_reference = (dates >= reference_first_day) & (dates <= reference_last_day)
    habitual = typical[in_reference].groupby(level="customer").median()
    habitual_per_day = habitual.reindex(customers).to_numpy()
    low = typical.to_numpy() < ratio * habitual_per_day

    new_customer = np.r_[True, customers[1:] != customers[:-1]]
    missing_day = np.r_[True, (dates[1:] - dates[:-1]) != pd.Timedelta(days=1)]
    flag_changes = np.r_[True, low[1:] != low[:-1]]
    run = np.cumsum(new_customer | missing_day | flag_changes)
    run_length = np.bincount(run)[run]
    return pd.Series(low & (run_length >= min_days), index=typical.index, name="casa_vacia")
