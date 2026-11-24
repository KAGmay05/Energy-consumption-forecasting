"""Preparación y ejecución de la evaluación de un pliegue.

prepare carga una vez todo lo que no depende del modelo: el panel, el ForecastGrid, los valores
reales, la máscara, las escalas y los segmentos. evaluate_forecast evalúa la matriz de pronósticos
de un modelo con ese contexto, y combine junta las tablas de varios modelos.

El pliegue de test solo se prepara con allow_test=True: se usa una sola vez por modelo, cuando su
configuración ya está fijada con validación (docs/modelado/decisiones.md, sección 2).
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.evaluation.metrics import energy_scale, evaluate, mase_scale
from src.evaluation.panel import DATA_PATH, Panel, load_panel
from src.evaluation.segments import day_segments, grid_segments, load_daily_max_temperature
from src.evaluation.splits import ForecastGrid, Fold, evaluation_mask, forecast_grid, gather
from src.features.vacancy import flag_vacant_days, typical_hour

RESULTS_DIR = Path(__file__).resolve().parents[2] / "data" / "results"


@dataclass(frozen=True)
class EvaluationContext:
    """Todo lo que necesita la evaluación de un pliegue, salvo los pronósticos."""
    fold: Fold
    panel: Panel
    grid: ForecastGrid
    y_true: np.ndarray
    mask: np.ndarray
    scale: np.ndarray
    energy_scale: np.ndarray
    segments: dict


def prepare(fold, allow_test=False, path=DATA_PATH):
    """Carga los datos y prepara la evaluación de un pliegue."""
    if fold.name == "test" and not allow_test:
        raise PermissionError("El pliegue de test se usa una sola vez por modelo: pasar allow_test=True")
    panel = load_panel(columns=("demand_kwh", "cl_estimated"), path=path)
    grid = forecast_grid(fold)

    gc = pd.read_parquet(path, columns=["customer", "timestamp_utc", "gc_kwh"])
    vacancy = flag_vacant_days(typical_hour(gc))
    dates = pd.date_range(fold.eval_first_day, fold.eval_last_day)
    segments = grid_segments(grid, day_segments(dates, load_daily_max_temperature()),
                             vacancy=vacancy, customers=panel.customers)

    return EvaluationContext(
        fold=fold, panel=panel, grid=grid,
        y_true=gather(panel, "demand_kwh", grid),
        mask=evaluation_mask(panel, grid),
        scale=mase_scale(panel, fold),
        energy_scale=energy_scale(panel, fold),
        segments=segments,
    )


def evaluate_forecast(context, y_pred):
    """Tablas de métricas de una matriz de pronósticos (hogares, orígenes, MAX_STEPS)."""
    return evaluate(context.y_true, y_pred, context.mask, context.grid, context.scale, context.energy_scale,
                    context.segments)


def combine(results):
    """Junta las tablas de varios modelos: dict modelo -> tablas pasa a dict tabla -> DataFrame con nivel modelo."""
    names = next(iter(results.values())).keys()
    return {table: pd.concat({model: tables[table] for model, tables in results.items()}, names=["modelo"])
            for table in names}


def save_tables(tables, output_dir, prefix):
    """Guarda cada tabla como parquet: output_dir/prefix_tabla.parquet."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        path = output_dir / f"{prefix}_{name}.parquet"
        table.reset_index().to_parquet(path, index=False)
        print(f"Guardado: {path}")
