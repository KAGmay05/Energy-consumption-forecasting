import numpy as np
import pandas as pd
import pytest

from src.evaluation.metrics import (daily_energy_sums, energy_scale, evaluate, group_metrics, mase_scale,
                                    summarize_daily_energy)
from src.evaluation.panel import build_panel
from src.evaluation.splits import VALIDATION, Fold, evaluation_mask, forecast_grid, gather
from tests.conftest import hours_between

# Dos hogares, un origen y cuatro horas
Y_TRUE = np.array([[[1.0, 1.0, 1.0, 1.0]], [[2.0, 2.0, 2.0, 2.0]]])
Y_PRED = np.array([[[2.0, 1.0, 1.0, 1.0]], [[1.0, 1.0, 2.0, 2.0]]])
ALL = np.ones(Y_TRUE.shape, dtype=bool)
SCALE = np.array([0.5, 1.0])


def test_metrics_by_household_then_summarized():
    table = group_metrics(Y_TRUE, Y_PRED, ALL, np.zeros((1, 4), dtype=int), ["todo"], SCALE).loc["todo"]
    # hogar 1: MAE 0,25, MASE 0,5, sesgo +25 %; hogar 2: MAE 0,5, MASE 0,5, sesgo −25 %
    assert table["hogares"] == 2 and table["horas"] == 8
    assert table["mase_mediana"] == pytest.approx(0.5) and table["mase_media"] == pytest.approx(0.5)
    assert table["mae_kwh"] == pytest.approx(3 / 8)
    assert table["sesgo_mediana"] == pytest.approx(0.0)
    assert table["sesgo_total"] == pytest.approx(100 * (1 - 2) / 12)


def test_mask_and_negative_labels_leave_hours_out():
    mask = ALL.copy()
    mask[0, 0, 0] = False
    labels = np.array([[0, 0, 1, -1]])
    table = group_metrics(Y_TRUE, Y_PRED, mask, labels, ["a", "b"], SCALE)
    assert table.loc["a", "horas"] == 3 and table.loc["b", "horas"] == 2
    assert table.loc["b", "mase_media"] == pytest.approx(0.0)
    assert table.loc["a", "mae_kwh"] == pytest.approx(2 / 3)


def test_missing_prediction_in_an_evaluated_hour_raises():
    y_pred = Y_PRED.copy()
    y_pred[0, 0, 3] = np.nan
    with pytest.raises(ValueError):
        group_metrics(Y_TRUE, y_pred, ALL, np.zeros((1, 4), dtype=int), ["todo"], SCALE)
    mask = ALL.copy()
    mask[0, 0, 3] = False
    group_metrics(Y_TRUE, y_pred, mask, np.zeros((1, 4), dtype=int), ["todo"], SCALE)


def test_daily_energy_only_counts_complete_days():
    y_true = np.array([[[1.0, 1.0, 1.0, 2.0, 2.0, np.nan]]])
    y_pred = np.array([[[1.0, 1.0, 2.0, 2.0, 2.0, np.nan]]])
    mask = np.array([[[True, True, True, True, False, False]]])
    day = np.array([[1, 1, 1, 2, 2, 0]])
    real, predicted, complete = daily_energy_sums(y_true, y_pred, mask, day)
    assert complete[0, 0, 0] and not complete[0, 0, 1:].any()
    assert real[0, 0, 0] == 3 and predicted[0, 0, 0] == 4
    table = summarize_daily_energy(real, predicted, complete, np.array([10.0]))
    assert table.loc[1, "error_energia_mediana"] == pytest.approx(10.0)
    assert table.loc[1, "sesgo_energia_total"] == pytest.approx(100 / 3)
    assert table.loc[2, "hogares"] == 0


def test_mase_scale_is_the_24_hour_persistence_error():
    stamps = hours_between(pd.Timestamp("2011-01-10"), pd.Timestamp("2011-01-12"))
    demand = np.tile(np.linspace(0.2, 1.4, 24), 3)
    demand[60] += 2.4  # una sola hora del tercer día se separa del día anterior
    panel = build_panel(pd.DataFrame({"customer": 1, "timestamp_utc": stamps, "demand_kwh": demand}), ["demand_kwh"])
    fold = Fold("prueba", pd.Timestamp("2011-01-10"), pd.Timestamp("2011-01-12"),
                pd.Timestamp("2011-02-01"), pd.Timestamp("2011-02-28"))
    assert mase_scale(panel, fold)[0] == pytest.approx(2.4 / 48)
    assert energy_scale(panel, fold)[0] == pytest.approx(24 * demand.mean())


def test_evaluate_on_a_whole_fold(validation_panel):
    grid = forecast_grid(VALIDATION)
    y_true = gather(validation_panel, "demand_kwh", grid)
    mask = evaluation_mask(validation_panel, grid)
    scale = mase_scale(validation_panel, VALIDATION)
    daily = energy_scale(validation_panel, VALIDATION)

    perfect = evaluate(y_true, y_true, mask, grid, scale, daily)
    assert np.allclose(perfect["por_dia"]["mase_media"], 0)
    assert np.allclose(perfect["energia_diaria"]["error_energia_media"], 0)

    tables = evaluate(y_true, 1.1 * y_true, mask, grid, scale, daily)
    assert set(tables) == {"por_paso", "por_dia", "por_hora", "noche", "energia_diaria"}
    assert len(tables["por_paso"]) == 337 and len(tables["por_dia"]) == 14 and len(tables["noche"]) == 2
    assert np.allclose(tables["por_dia"]["sesgo_total"], 10)
    assert np.allclose(tables["energia_diaria"]["sesgo_energia_total"], 10)
    assert (tables["por_dia"]["hogares"] == 2).all()
    assert tables["por_paso"]["horas"].sum() == mask.sum()
