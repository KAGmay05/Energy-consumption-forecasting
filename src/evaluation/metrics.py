"""Métricas de los modelos de consumo (docs/modelado/decisiones.md, sección 3).

Los pronósticos son matrices (hogares, orígenes, MAX_STEPS) alineadas con un ForecastGrid, y la
máscara de evaluation_mask indica qué horas cuentan. Cada métrica se calcula primero en cada hogar
y después se resume entre hogares:

- mase_mediana y mase_media: mediana y media del MASE de los hogares.
- mae_kwh: error absoluto medio de todas las horas juntas, en kWh.
- sesgo_mediana: mediana del sesgo de los hogares, en %.
- sesgo_total: sesgo de todas las horas juntas, en %.

El sesgo es (Σ pronóstico − Σ real) / Σ real: positivo si el modelo sobrestima el consumo.
"""
import warnings

import numpy as np
import pandas as pd

from src.evaluation.splits import HORIZON_DAYS, MAX_STEPS

NIGHT_HOURS = list(range(18, 24)) + list(range(0, 6))


def mase_scale(panel, fold, column="demand_kwh"):
    """Escala del MASE de cada hogar: MAE de la persistencia de 24 h en las horas del periodo de ajuste."""
    values = panel[column]
    in_fit = fold.fit_hours(panel.timestamps)[24:]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        scale = np.nanmean(np.abs(values[:, 24:] - values[:, :-24])[:, in_fit], axis=1)
    if not np.all(np.isfinite(scale) & (scale > 0)):
        raise ValueError("Hay hogares sin escala del MASE en el periodo de ajuste")
    return scale


def energy_scale(panel, fold, column="demand_kwh"):
    """Energía diaria media de cada hogar en el periodo de ajuste: 24 veces su consumo horario medio."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        scale = 24 * np.nanmean(panel[column][:, fold.fit_hours(panel.timestamps)], axis=1)
    if not np.all(np.isfinite(scale) & (scale > 0)):
        raise ValueError("Hay hogares sin consumo en el periodo de ajuste")
    return scale


def _check_inputs(y_true, y_pred, mask):
    if not (y_true.shape == y_pred.shape == mask.shape):
        raise ValueError(f"Formas distintas: {y_true.shape}, {y_pred.shape}, {mask.shape}")
    if np.isnan(y_true[mask]).any():
        raise ValueError("Faltan valores reales en horas que se evalúan")
    if np.isnan(y_pred[mask]).any():
        raise ValueError("El modelo no da pronóstico en horas que se evalúan")


def household_sums_by_grouping(y_true, y_pred, mask, groupings):
    """Sumas de cada hogar y grupo para varias agrupaciones, recorriendo cada hogar una sola vez.

    groupings es un dict nombre -> (labels, n_groups). labels asigna a cada hora un grupo, de 0 a
    n_groups − 1, o −1 para dejarla fuera. Puede tener la forma de y_true o una que se difunda a
    ella, como (orígenes, MAX_STEPS). Devuelve un dict nombre -> sumas, donde las sumas son matrices
    (hogares, n_groups) de horas, error_abs, error y real.
    """
    _check_inputs(y_true, y_pred, mask)
    n_customers = y_true.shape[0]
    prepared = {}
    for name, (labels, n_groups) in groupings.items():
        labels = np.broadcast_to(labels, y_true.shape)
        if labels.max() >= n_groups:
            raise ValueError(f"{name}: hay etiquetas mayores que el número de grupos")
        sums = {total: np.zeros((n_customers, n_groups)) for total in ("horas", "error_abs", "error", "real")}
        prepared[name] = (labels, n_groups, sums)

    for customer in range(n_customers):
        use = mask[customer]
        real = y_true[customer][use].astype("float64")
        error = y_pred[customer][use].astype("float64") - real
        for labels, n_groups, sums in prepared.values():
            groups = labels[customer][use].astype("int64")
            keep = groups >= 0
            groups = groups[keep]
            sums["horas"][customer] = np.bincount(groups, minlength=n_groups)
            sums["error_abs"][customer] = np.bincount(groups, weights=np.abs(error[keep]), minlength=n_groups)
            sums["error"][customer] = np.bincount(groups, weights=error[keep], minlength=n_groups)
            sums["real"][customer] = np.bincount(groups, weights=real[keep], minlength=n_groups)
    return {name: sums for name, (_, _, sums) in prepared.items()}


def household_sums(y_true, y_pred, mask, labels, n_groups):
    """Sumas de cada hogar y grupo para una sola agrupación (household_sums_by_grouping)."""
    return household_sums_by_grouping(y_true, y_pred, mask, {"grupos": (labels, n_groups)})["grupos"]


def summarize(sums, scale, groups):
    """Resume entre hogares las sumas de household_sums: una fila por grupo."""
    hours = sums["horas"]
    has_hours = hours > 0
    with warnings.catch_warnings(), np.errstate(divide="ignore", invalid="ignore"):
        warnings.simplefilter("ignore", RuntimeWarning)  # grupos sin ningún hogar
        mase = np.where(has_hours, sums["error_abs"] / hours / scale[:, None], np.nan)
        bias = np.where(has_hours & (sums["real"] > 0), sums["error"] / sums["real"], np.nan)
        return pd.DataFrame({
            "hogares": has_hours.sum(axis=0),
            "horas": hours.sum(axis=0).astype("int64"),
            "mase_mediana": np.nanmedian(mase, axis=0),
            "mase_media": np.nanmean(mase, axis=0),
            "mae_kwh": sums["error_abs"].sum(axis=0) / hours.sum(axis=0),
            "sesgo_mediana": 100 * np.nanmedian(bias, axis=0),
            "sesgo_total": 100 * sums["error"].sum(axis=0) / sums["real"].sum(axis=0),
        }, index=pd.Index(groups))


def group_metrics(y_true, y_pred, mask, labels, groups, scale):
    """Métricas por grupo: household_sums seguido de summarize."""
    groups = pd.Index(groups)
    return summarize(household_sums(y_true, y_pred, mask, labels, len(groups)), scale, groups)


def daily_energy_sums(y_true, y_pred, mask, day):
    """Energía real y pronosticada de cada hogar, origen y día de horizonte.

    day es ForecastGrid.day. Devuelve real, pronostico y completo, con forma (hogares, orígenes,
    HORIZON_DAYS). Un día está completo si todas sus horas entran en la máscara; solo esos días
    cuentan en el error de la energía diaria.
    """
    _check_inputs(y_true, y_pred, mask)
    one_hot = (day[:, :, None] == np.arange(1, HORIZON_DAYS + 1)).astype("float64")
    hours_in_day = one_hot.sum(axis=1)
    shape = (y_true.shape[0], y_true.shape[1], HORIZON_DAYS)
    real, predicted, complete = np.empty(shape), np.empty(shape), np.empty(shape, dtype=bool)
    for customer in range(y_true.shape[0]):
        use = mask[customer]
        real[customer] = np.einsum("oh,ohk->ok", np.where(use, y_true[customer], 0.0), one_hot)
        predicted[customer] = np.einsum("oh,ohk->ok", np.where(use, y_pred[customer], 0.0), one_hot)
        valid_hours = np.einsum("oh,ohk->ok", use.astype("float64"), one_hot)
        complete[customer] = (valid_hours == hours_in_day) & (hours_in_day > 0)
    return real, predicted, complete


def summarize_daily_energy(real, predicted, complete, energy_scale):
    """Error de la energía diaria por día de horizonte, en % de la energía diaria media del hogar.

    - error_energia_mediana y error_energia_media: mediana y media entre hogares del error absoluto
      medio de cada hogar.
    - sesgo_energia_mediana: mediana entre hogares del error medio con signo.
    - sesgo_energia_total: (Σ pronóstico − Σ real) / Σ real de todos los días completos juntos.
    """
    error = np.where(complete, (predicted - real) / energy_scale[:, None, None], np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # hogares sin días completos
        mean_abs = np.nanmean(np.abs(error), axis=1)
        mean_signed = np.nanmean(error, axis=1)
        return pd.DataFrame({
            "hogares": np.isfinite(mean_abs).sum(axis=0),
            "dias": complete.sum(axis=(0, 1)),
            "error_energia_mediana": 100 * np.nanmedian(mean_abs, axis=0),
            "error_energia_media": 100 * np.nanmean(mean_abs, axis=0),
            "sesgo_energia_mediana": 100 * np.nanmedian(mean_signed, axis=0),
            "sesgo_energia_total": 100 * np.where(complete, predicted - real, 0).sum(axis=(0, 1))
                                   / np.where(complete, real, 0).sum(axis=(0, 1)),
        }, index=pd.Index(np.arange(1, HORIZON_DAYS + 1), name="dia"))


def evaluate(y_true, y_pred, mask, grid, scale, energy_scale, segments=None):
    """Todas las tablas de métricas de un modelo en un pliegue.

    segments es un dict nombre -> (etiquetas, categorías), como lo devuelve segments.grid_segments.
    Devuelve un dict de DataFrames: por_paso, por_dia, por_hora, noche, energia_diaria y, si se
    pasan segmentos, por_segmento.
    """
    groupings = {
        "por_paso": (np.broadcast_to(np.arange(MAX_STEPS), grid.day.shape), pd.Index(grid.steps, name="paso")),
        "por_dia": (grid.day.astype("int64") - 1, pd.Index(np.arange(1, HORIZON_DAYS + 1), name="dia")),
        "por_hora": (grid.hora_local, pd.Index(np.arange(24), name="hora_local")),
        "noche": (np.isin(grid.hora_local, NIGHT_HOURS).astype("int8"),
                  pd.Index(["de 06:00 a 18:00", "de 18:00 a 06:00"], name="franja")),
    }
    for name, (labels, categories) in (segments or {}).items():
        groupings[("segmento", name)] = (labels, pd.Index(categories))

    sums = household_sums_by_grouping(
        y_true, y_pred, mask, {name: (labels, len(groups)) for name, (labels, groups) in groupings.items()})
    tables = {name: summarize(sums[name], scale, groups)
              for name, (_, groups) in groupings.items() if not isinstance(name, tuple)}
    if segments:
        tables["por_segmento"] = pd.concat(
            {name: summarize(sums[("segmento", name)], scale, groupings[("segmento", name)][1]) for name in segments},
            names=["segmento", "valor"])
    tables["energia_diaria"] = summarize_daily_energy(*daily_energy_sums(y_true, y_pred, mask, grid.day),
                                                      energy_scale)
    return tables
