"""Referencias para horizontes de semanas y meses (docs/modelado/decisiones.md, sección 8).

A partir de unas dos semanas el pronóstico deja de referirse a horas concretas y pasa a describir
la energía de un periodo (estado_del_arte.md, sección 3.6). Aquí se pronostica la energía de un
bloque de días seguidos: 7 días (una semana) o 28 días (cuatro semanas, el "mes"). Con 28 días
cada bloque tiene cuatro veces cada día de la semana, y el año anterior se toma 364 días antes,
así que siempre se comparan los mismos días de la semana.

Cada bloque del año evaluado se pronostica con varias antelaciones. La antelación L son los días
entre el origen y el inicio del bloque (L = 0 si el bloque empieza el día del origen), así que el
origen es d0 = inicio − L y solo se usa la energía de los días anteriores a d0:

- reciente: la energía diaria media de los 7 días anteriores al origen, multiplicada por la
  longitud del bloque.
- año_anterior: la energía del mismo bloque 364 días antes. No depende de la antelación, y solo se
  usa si ese bloque termina antes del origen.

Los errores se dan en % de la energía media de un bloque del hogar en el periodo de ajuste.
"""
import warnings

import numpy as np
import pandas as pd

from src.evaluation.splits import local_midnight_utc
from src.features.calendar import local_date

BLOCK_DAYS = {"semana": 7, "mes": 28}
LEADS = [0, 7, 14, 28, 56, 91, 182, 273]
RECENT_DAYS = 7
YEAR_DAYS = 364


def daily_energy(panel, column="demand_kwh"):
    """Energía de cada hogar y día local: matriz (hogares, días) y las fechas de los días.

    Un día que no tiene todas sus horas (el primero del conjunto, los del hueco del hogar 2) vale NaN.
    """
    dates = local_date(panel.timestamps).to_numpy()
    days, starts = np.unique(dates, return_index=True)
    energy = np.add.reduceat(panel[column], starts, axis=1)
    hours = np.diff(np.r_[starts, len(dates)])
    days = pd.DatetimeIndex(days)
    expected = (local_midnight_utc(days + pd.Timedelta(days=1)) - local_midnight_utc(days)) // pd.Timedelta(hours=1)
    energy[:, hours != np.asarray(expected)] = np.nan
    if (np.diff(days) != pd.Timedelta(days=1)).any():
        raise ValueError("Los días del panel no son consecutivos")
    return energy, days


def estimated_cl_days(panel):
    """(hogares, días): el día tiene alguna hora con CL estimado. Mismo orden de días que daily_energy."""
    if "cl_estimated" not in panel.values:
        raise ValueError("El panel necesita la columna cl_estimated para excluir esos días")
    _, starts = np.unique(local_date(panel.timestamps).to_numpy(), return_index=True)
    return np.add.reduceat(panel["cl_estimated"].astype("int64"), starts, axis=1) > 0


def block_sums(energy, length):
    """Energía de los bloques de `length` días: la columna j es el bloque que empieza el día j.

    Un bloque con algún día sin dato vale NaN.
    """
    missing = np.isnan(energy)
    zeros = np.zeros((energy.shape[0], 1))
    total = np.concatenate([zeros, np.cumsum(np.where(missing, 0.0, energy), axis=1)], axis=1)
    gaps = np.concatenate([zeros, np.cumsum(missing, axis=1)], axis=1)
    sums = total[:, length:] - total[:, :-length]
    sums[(gaps[:, length:] - gaps[:, :-length]) > 0] = np.nan
    return sums


def block_forecasts(energy, days, fold, length, lead, target_energy=None):
    """Energía real y pronósticos de los bloques de un pliegue, para una longitud y una antelación.

    Los bloques empiezan cada día del año evaluado y terminan dentro de él. Los pronósticos usan
    energy; el valor real sale de target_energy si se pasa, que puede tener NaN en los días que no
    se evalúan. Devuelve real y un dict referencia -> pronóstico, todos con forma (hogares, bloques).
    """
    first = (fold.eval_first_day - days[0]).days
    last = (fold.eval_last_day - days[0]).days - length + 1
    starts = np.arange(first, last + 1)
    origins = starts - lead
    if (origins - RECENT_DAYS).min() < 0 or (starts - YEAR_DAYS).min() < 0:
        raise ValueError("No hay historia suficiente antes de los bloques")

    sums = block_sums(energy, length)
    recent = block_sums(energy, RECENT_DAYS)[:, origins - RECENT_DAYS] * length / RECENT_DAYS
    previous_year = sums[:, starts - YEAR_DAYS]
    if lead > YEAR_DAYS - length:
        previous_year = np.full_like(previous_year, np.nan)  # el bloque del año anterior no termina antes del origen
    real = sums if target_energy is None else block_sums(target_energy, length)
    return real[:, starts], {"reciente": recent, "año_anterior": previous_year}


def summarize_blocks(real, predicted, block_scale):
    """Resumen entre hogares del error de la energía de los bloques, en % de block_scale."""
    error = (predicted - real) / block_scale[:, None]
    valid = np.isfinite(error)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # hogares sin bloques
        mean_abs = np.nanmean(np.abs(error), axis=1)
        mean_signed = np.nanmean(error, axis=1)
    return {
        "hogares": int(np.isfinite(mean_abs).sum()),
        "bloques": int(valid.sum()),
        "error_mediana": 100 * np.nanmedian(mean_abs),
        "error_media": 100 * np.nanmean(mean_abs),
        "sesgo_mediana": 100 * np.nanmedian(mean_signed),
        "sesgo_total": 100 * np.where(valid, predicted - real, 0).sum() / np.where(valid, real, 0).sum(),
    }


def evaluate_blocks(panel, fold, energy_scale, leads=LEADS, column="demand_kwh"):
    """Tabla del error de cada referencia por bloque (semana o mes) y antelación.

    energy_scale es la energía diaria media de cada hogar en el periodo de ajuste
    (metrics.energy_scale); la de un bloque es esa energía por su longitud. Los bloques con algún
    día de CL estimado no se evalúan, aunque esos días sí sirven como historia.
    """
    energy, days = daily_energy(panel, column)
    target_energy = np.where(estimated_cl_days(panel), np.nan, energy)
    rows = []
    for block, length in BLOCK_DAYS.items():
        for lead in leads:
            real, forecasts = block_forecasts(energy, days, fold, length, lead, target_energy)
            for reference, predicted in forecasts.items():
                if np.isnan(predicted).all():
                    continue
                summary = summarize_blocks(real, predicted, length * energy_scale)
                rows.append({"bloque": block, "antelacion": lead, "referencia": reference, **summary})
    return pd.DataFrame(rows).set_index(["bloque", "antelacion", "referencia"])
