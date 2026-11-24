import numpy as np
import pandas as pd
import pytest

from src.evaluation.panel import Panel, build_panel
from src.evaluation.runner import prepare
from src.evaluation.splits import TEST, Fold, forecast_grid
from src.features.calendar import hour_calendar
from src.models.baselines import BASELINES, climatology, persistence, recent_days
from tests.conftest import hours_between

FOLD = Fold("prueba", pd.Timestamp("2011-01-01"), pd.Timestamp("2011-12-31"),
            pd.Timestamp("2012-01-01"), pd.Timestamp("2012-06-30"))
STAMPS = hours_between(pd.Timestamp("2011-01-01"), pd.Timestamp("2012-06-30"))


def calendar_demand(stamps):
    """Consumo que solo depende de la estación, el tipo de día y la hora local."""
    hours = hour_calendar(stamps)
    return (1 + hours["hora_local"].to_numpy() / 10 + 0.5 * ~hours["laborable"].to_numpy()
            + 0.2 * hours["estacion"].cat.codes.to_numpy())


def make_panel(demand_by_customer):
    frames = [pd.DataFrame({"customer": customer, "timestamp_utc": STAMPS, "demand_kwh": demand})
              for customer, demand in demand_by_customer.items()]
    return build_panel(pd.concat(frames, ignore_index=True), ["demand_kwh"])


@pytest.fixture(scope="module")
def grid():
    return forecast_grid(FOLD)


@pytest.fixture(scope="module")
def index_panel():
    """El consumo de cada hora es su posición en el panel: así se ve qué hora copia cada referencia."""
    position = np.arange(len(STAMPS), dtype="float64")
    return make_panel({1: position, 2: position + 0.5})


@pytest.fixture(scope="module")
def calendar_panel():
    demand = calendar_demand(STAMPS)
    return make_panel({1: demand, 2: 2 * demand})


def expected_source(index_panel, grid, period):
    steps = grid.steps
    origin = index_panel.positions(grid.origins)[:, None]
    return np.where(grid.in_horizon, origin + steps - period * np.ceil(steps / period), np.nan)


@pytest.mark.parametrize("period", [24, 168])
def test_persistence_copies_the_same_hour_of_the_last_period(index_panel, grid, period):
    forecast = persistence(index_panel, grid, period)
    np.testing.assert_array_equal(forecast[0], expected_source(index_panel, grid, period))
    np.testing.assert_array_equal(forecast[1], expected_source(index_panel, grid, period) + 0.5)


@pytest.mark.parametrize("statistic", ["mean", "median"])
def test_recent_days_summarize_the_same_hour_of_the_last_7_days(index_panel, grid, statistic):
    # Con el consumo igual a la posición, la misma hora de los 7 días es p, p − 24, ..., p − 144
    forecast = recent_days(index_panel, grid, 7, statistic)
    np.testing.assert_array_equal(forecast[0], expected_source(index_panel, grid, 24) - 72)


def test_climatology_recovers_a_calendar_pattern(calendar_panel, grid):
    forecast = climatology(calendar_panel, grid)
    target = pd.DatetimeIndex(grid.target_utc[grid.in_horizon]).tz_localize("UTC")
    np.testing.assert_allclose(forecast[0][grid.in_horizon], calendar_demand(target))
    np.testing.assert_allclose(forecast[1][grid.in_horizon], 2 * calendar_demand(target))
    assert np.isnan(forecast[:, ~grid.in_horizon]).all()


def hide(panel, hidden):
    """Copia del panel con NaN en las horas marcadas por hidden (vector sobre el eje de tiempo)."""
    values = panel["demand_kwh"].copy()
    values[:, hidden] = np.nan
    return Panel(panel.customers, panel.timestamps, panel.present, {"demand_kwh": values})


@pytest.mark.parametrize("name", [name for name in BASELINES if name != "climatologia"])
def test_no_baseline_reads_hours_after_the_origin(grid, name):
    noisy = make_panel({1: np.random.default_rng(1).gamma(2.0, 0.4, len(STAMPS))})
    forecast = BASELINES[name](noisy, grid)
    origins = noisy.positions(grid.origins)
    for row in [0, len(origins) // 2, len(origins) - 1]:
        without_future = hide(noisy, np.arange(len(STAMPS)) > origins[row])
        np.testing.assert_array_equal(BASELINES[name](without_future, grid)[:, row], forecast[:, row])
        assert not np.isnan(forecast[:, row][:, grid.in_horizon[row]]).any()


def test_climatology_only_reads_the_fit_period(calendar_panel, grid):
    outside_fit = ~FOLD.fit_hours(calendar_panel.timestamps)
    np.testing.assert_array_equal(climatology(hide(calendar_panel, outside_fit), grid),
                                  climatology(calendar_panel, grid))


def test_baselines_return_one_matrix_per_grid(index_panel, grid):
    for name, forecast in BASELINES.items():
        assert forecast(index_panel, grid).shape == (2,) + grid.day.shape, name


def test_test_fold_needs_explicit_permission():
    with pytest.raises(PermissionError):
        prepare(TEST)
