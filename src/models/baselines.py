"""Modelos de referencia (docs/modelado/decisiones.md, sección 7).

Las referencias no se entrenan. Cada pronóstico sale del consumo de las horas que terminan en el
origen t0 o antes, o de la climatología del periodo de ajuste. Todas devuelven una matriz
(hogares, orígenes, MAX_STEPS) alineada con el ForecastGrid, con NaN fuera del horizonte, y los
retardos se cuentan en horas reales.

- persistencia_24h: y(t0 + h − 24·⌈h/24⌉), la misma hora del último día observado.
- persistencia_168h: y(t0 + h − 168·⌈h/168⌉), la misma hora y día de la última semana observada.
- media_7_dias y mediana_7_dias: media o mediana de la misma hora en los 7 días anteriores al origen.
- climatologia: media del hogar en el periodo de ajuste para la misma estación, tipo de día
  (laborable o no laborable) y hora local.

Ejecutar como módulo para evaluarlas en el pliegue de validación:

    python -m src.models.baselines
"""
import argparse

import numpy as np
import pandas as pd

from src.evaluation.runner import RESULTS_DIR, combine, evaluate_forecast, prepare, save_tables
from src.evaluation.splits import FOLDS
from src.features.calendar import SEASON_ORDER, hour_calendar
from src.models.energy_baselines import evaluate_blocks

CLIMATOLOGY_CELLS = len(SEASON_ORDER) * 2 * 24


def recent_hours(panel, grid, hours, column="demand_kwh"):
    """Consumo de las `hours` horas que terminan en cada origen: (hogares, orígenes, hours).

    La última columna es la hora que termina en t0. No se lee ninguna hora posterior al origen.
    """
    positions = panel.positions(grid.origins)[:, None] + np.arange(-hours + 1, 1)[None, :]
    if positions.min() < 0:
        raise ValueError(f"No hay {hours} horas de historia antes del primer origen")
    return panel[column][:, positions]


def repeat_over_horizon(block, grid, period):
    """Repite un bloque de `period` horas por todo el horizonte.

    block tiene forma (hogares, orígenes, period) y su última columna es la hora que termina en t0.
    El paso h toma la columna de la hora t0 + h − period·⌈h/period⌉.
    """
    steps = grid.steps
    column = (steps - period * np.ceil(steps / period)).astype("int64") + period - 1
    forecast = block[:, :, column]
    forecast[:, ~grid.in_horizon] = np.nan
    return forecast


def persistence(panel, grid, period, column="demand_kwh"):
    """Persistencia estacional: copia la misma hora del último periodo de `period` horas observado."""
    return repeat_over_horizon(recent_hours(panel, grid, period, column), grid, period)


def recent_days(panel, grid, days=7, statistic="mean", column="demand_kwh"):
    """Media o mediana de la misma hora en los `days` días anteriores al origen."""
    block = recent_hours(panel, grid, 24 * days, column)
    block = block.reshape(block.shape[0], block.shape[1], days, 24)
    if statistic == "mean":
        summary = block.mean(axis=2)
    elif statistic == "median":
        summary = np.median(block, axis=2)
    else:
        raise ValueError(f"Estadístico desconocido: {statistic}")
    return repeat_over_horizon(summary, grid, 24)


def climatology_cells(timestamps_utc):
    """Combinación de estación, tipo de día y hora local de cada hora, de 0 a CLIMATOLOGY_CELLS − 1."""
    hours = hour_calendar(timestamps_utc)
    season = hours["estacion"].cat.codes.to_numpy().astype("int64")
    not_working = (~hours["laborable"].to_numpy()).astype("int64")
    return season * 48 + not_working * 24 + hours["hora_local"].to_numpy().astype("int64")


def climatology(panel, grid, column="demand_kwh"):
    """Media de cada hogar en el periodo de ajuste del pliegue para la misma estación, tipo de día y hora local."""
    fit = grid.fold.fit_hours(panel.timestamps)
    values = panel[column][:, fit]
    known = ~np.isnan(values)
    one_hot = np.zeros((int(fit.sum()), CLIMATOLOGY_CELLS))
    one_hot[np.arange(one_hot.shape[0]), climatology_cells(panel.timestamps[fit])] = 1.0
    counts = known.astype("float64") @ one_hot
    if (counts == 0).any():
        raise ValueError("Hay combinaciones de estación, tipo de día y hora sin horas en el periodo de ajuste")
    means = (np.where(known, values, 0.0) @ one_hot) / counts

    target = pd.DatetimeIndex(grid.target_utc.ravel()).tz_localize("UTC")
    forecast = means[:, climatology_cells(target).reshape(grid.target_utc.shape)]
    forecast[:, ~grid.in_horizon] = np.nan
    return forecast


BASELINES = {
    "persistencia_24h": lambda panel, grid: persistence(panel, grid, 24),
    "persistencia_168h": lambda panel, grid: persistence(panel, grid, 168),
    "media_7_dias": lambda panel, grid: recent_days(panel, grid, 7, "mean"),
    "mediana_7_dias": lambda panel, grid: recent_days(panel, grid, 7, "median"),
    "climatologia": climatology,
}


def run(fold, allow_test=False, output_dir=RESULTS_DIR):
    """Evalúa en un pliegue las referencias horarias y las de semanas y meses, y guarda las tablas en output_dir.

    La tabla bloques tiene el error de la energía de bloques de 7 y 28 días según la antelación
    (energy_baselines.py).
    """
    context = prepare(fold, allow_test=allow_test)
    results = {}
    for name, forecast in BASELINES.items():
        results[name] = evaluate_forecast(context, forecast(context.panel, context.grid))
        print(f"Evaluada: {name}")
    tables = combine(results)
    tables["bloques"] = evaluate_blocks(context.panel, fold, context.energy_scale)
    print("Evaluadas: referencias de semanas y meses")
    save_tables(tables, output_dir, f"referencias_{fold.name}")
    return tables


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evalúa los modelos de referencia")
    parser.add_argument("--fold", choices=list(FOLDS), default="validacion")
    parser.add_argument("--confirmo-test", action="store_true",
                        help="Necesario para evaluar en test, que se usa una sola vez (decisiones.md, sección 2)")
    args = parser.parse_args()

    tables = run(FOLDS[args.fold], allow_test=args.confirmo_test)
    by_day = tables["por_dia"]
    pd.set_option("display.width", 200)
    print("\nMASE por día de horizonte (mediana de los hogares):")
    print(by_day["mase_mediana"].unstack("modelo").round(3).to_string())
    print("\nSesgo de todas las horas juntas, en %:")
    print(by_day["sesgo_total"].unstack("modelo").round(2).to_string())
