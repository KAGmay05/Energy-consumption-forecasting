import numpy as np
import pandas as pd

from src.evaluation.segments import daily_max_temperature, day_segments, grid_segments
from src.evaluation.splits import VALIDATION, forecast_grid
from tests.conftest import hours_between


def test_daily_max_uses_the_local_day():
    stamps = hours_between(pd.Timestamp("2012-01-10"), pd.Timestamp("2012-01-11"))
    temperature = pd.Series(20.0, index=stamps)
    temperature.iloc[23] = 35.0  # 23:00 a 24:00 del día 10, hora local
    daily = daily_max_temperature(temperature)
    assert daily[pd.Timestamp("2012-01-10")] == 35 and daily[pd.Timestamp("2012-01-11")] == 20


def test_grid_segments():
    grid = forecast_grid(VALIDATION)
    dates = pd.date_range("2011-07-01", "2012-06-30")
    temperature = pd.Series(20.0, index=dates)
    temperature[pd.Timestamp("2012-01-05")] = 33.0
    segments = day_segments(dates, temperature)
    vacancy = pd.Series(True, index=pd.MultiIndex.from_tuples([(7, pd.Timestamp("2011-07-02"))],
                                                              names=["customer", "fecha_local"]))
    labels = grid_segments(grid, segments, vacancy=vacancy, customers=np.array([7, 8]))

    assert set(labels) == {"tipo_dia", "estacion", "navidad", "calor", "casa_vacia"}
    codes, categories = labels["calor"]
    assert codes.shape == grid.day.shape and categories == ["no", "sí"]
    hot = grid.fecha_local == np.datetime64("2012-01-05")
    assert (codes[hot & grid.in_horizon] == 1).all() and (codes[~hot & grid.in_horizon] == 0).all()
    assert (codes[~grid.in_horizon] == -1).all()

    vacant, _ = labels["casa_vacia"]
    second_day = grid.fecha_local == np.datetime64("2011-07-02")
    assert vacant.shape == (2,) + grid.day.shape
    assert (vacant[0][second_day & grid.in_horizon] == 1).all() and (vacant[1][grid.in_horizon] == 0).all()
