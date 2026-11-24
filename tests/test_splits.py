import numpy as np
import pandas as pd
import pytest

from src.evaluation.splits import (MAX_STEPS, TEST, VALIDATION, evaluable_pairs, evaluation_mask, forecast_grid,
                                   gather)
from tests.conftest import CL_ESTIMATED_DAY, GAP_DAY


@pytest.fixture(scope="module")
def grid():
    return forecast_grid(VALIDATION)


def origin_index(day):
    return VALIDATION.origin_dates().get_loc(pd.Timestamp(day))


def test_origins():
    for fold, count, last in [(VALIDATION, 353, "2012-06-17"), (TEST, 352, "2013-06-17")]:
        dates = fold.origin_dates()
        assert len(dates) == count and dates[-1] == pd.Timestamp(last)
    origins = VALIDATION.origins()
    assert origins[0] == pd.Timestamp("2011-06-30 14:00", tz="UTC")  # 00:00 local en horario estándar
    assert origins[origin_index("2012-01-15")] == pd.Timestamp("2012-01-14 13:00", tz="UTC")  # horario de verano


def test_horizon_length_changes_only_with_daylight_saving(grid):
    hours = grid.in_horizon.sum(axis=1)
    assert hours[origin_index("2011-07-01")] == 336
    assert hours[origin_index("2011-09-25")] == 335  # incluye el 2-oct-2011, inicio del horario de verano
    assert hours[origin_index("2012-03-25")] == 337  # incluye el 1-abr-2012, fin del horario de verano
    assert (hours != 336).sum() == 28


def test_days_and_hours_of_the_horizon(grid):
    first = origin_index("2011-07-01")
    assert grid.day[first, 0] == 1 and grid.hora_local[first, 0] == 0
    assert grid.day[first, 335] == 14 and grid.hora_local[first, 335] == 23
    assert grid.day[first, 336] == 0 and not grid.in_horizon[first, 336]
    assert grid.day.shape == (353, MAX_STEPS)
    assert set(np.unique(grid.day[grid.in_horizon])) == set(range(1, 15))


def test_last_test_target_is_the_last_hour_of_the_data():
    test_grid = forecast_grid(TEST)
    last_target = test_grid.target_utc[-1][test_grid.in_horizon[-1]].max()
    assert pd.Timestamp(last_target) == pd.Timestamp("2013-06-30 14:00")


def test_pairs_with_missing_days_are_not_evaluated(validation_panel):
    pairs = evaluable_pairs(validation_panel, VALIDATION)
    assert pairs[0].all()
    excluded = VALIDATION.origin_dates()[~pairs[1]]
    # el día que falta cae en el horizonte (d0 a d0 + 13) o en los 28 días anteriores
    assert excluded[0] == GAP_DAY - pd.Timedelta(days=13)
    assert excluded[-1] == GAP_DAY + pd.Timedelta(days=28)
    assert len(excluded) == 42


def test_estimated_cl_hours_are_masked(validation_panel, grid):
    mask = evaluation_mask(validation_panel, grid)
    origin = origin_index(CL_ESTIMATED_DAY - pd.Timedelta(days=5))
    estimated = grid.fecha_local[origin] == np.datetime64(CL_ESTIMATED_DAY)
    assert not mask[0, origin][estimated].any()
    assert mask[0, origin][grid.in_horizon[origin] & ~estimated].all()
    assert mask[1, origin][grid.in_horizon[origin]].all()
    assert not (mask & ~grid.in_horizon).any()


def test_gather_matches_the_panel(validation_panel, grid):
    values = gather(validation_panel, "demand_kwh", grid)
    origin = origin_index("2011-07-01")
    position = validation_panel.timestamps.get_loc(pd.Timestamp("2011-06-30 15:00", tz="UTC"))
    assert values[0, origin, 0] == validation_panel["demand_kwh"][0, position]
    assert np.isnan(values[:, ~grid.in_horizon]).all()
