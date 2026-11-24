import numpy as np
import pandas as pd
import pytest

from src.evaluation.metrics import energy_scale
from src.evaluation.panel import build_panel
from src.evaluation.splits import VALIDATION
from src.features.calendar import local_date
from src.models.energy_baselines import LEADS, block_sums, daily_energy, evaluate_blocks
from tests.conftest import hours_between

STAMPS = hours_between(pd.Timestamp("2010-07-01"), pd.Timestamp("2012-06-30"))
ESTIMATED_DAY = pd.Timestamp("2012-03-01")


def one_kwh_per_day_panel(second_year_factor=1.0):
    """Un hogar que consume 1 kWh cada día del primer año y second_year_factor kWh cada día del segundo.

    Cada hora consume 1 / (horas del día), así que los días de 23 y 25 horas también suman 1 kWh.
    """
    days = pd.Series(local_date(STAMPS))
    demand = 1.0 / days.map(days.value_counts()).to_numpy()
    demand = np.where(days >= VALIDATION.eval_first_day, second_year_factor * demand, demand)
    data = pd.DataFrame({"customer": 1, "timestamp_utc": STAMPS, "demand_kwh": demand,
                         "cl_estimated": np.asarray(days == ESTIMATED_DAY)})
    return build_panel(data, ["demand_kwh", "cl_estimated"])


def test_daily_energy_handles_daylight_saving_and_incomplete_days():
    energy, days = daily_energy(one_kwh_per_day_panel())
    assert days[0] == pd.Timestamp("2010-07-01") and len(days) == 731
    np.testing.assert_allclose(energy, 1.0)

    partial = one_kwh_per_day_panel()
    values = partial["demand_kwh"].copy()
    values[0, :5] = np.nan  # faltan horas del primer día
    energy, _ = daily_energy(type(partial)(partial.customers, partial.timestamps, partial.present,
                                           {"demand_kwh": values}))
    assert np.isnan(energy[0, 0]) and np.isfinite(energy[0, 1:]).all()


def test_block_sums():
    sums = block_sums(np.array([[1.0, 2.0, np.nan, 4.0, 5.0]]), 2)
    np.testing.assert_array_equal(sums, [[3.0, np.nan, np.nan, 9.0]])


def test_constant_consumption_has_no_error():
    panel = one_kwh_per_day_panel()
    table = evaluate_blocks(panel, VALIDATION, energy_scale(panel, VALIDATION))
    assert set(table.index.get_level_values("antelacion")) == set(LEADS)
    np.testing.assert_allclose(table["error_mediana"], 0, atol=1e-9)
    np.testing.assert_allclose(table["sesgo_total"], 0, atol=1e-9)


def test_a_drop_in_the_second_year_shows_as_bias_of_the_previous_year():
    panel = one_kwh_per_day_panel(second_year_factor=0.9)
    table = evaluate_blocks(panel, VALIDATION, energy_scale(panel, VALIDATION))
    previous = table.xs("año_anterior", level="referencia")
    # 0,1 kWh de más por día sobre 1 kWh. No es exacto porque, por el 29 de febrero de 2012, el bloque
    # del año anterior de las últimas semanas de junio llega al 1 y 2 de julio de 2011, ya en el segundo año.
    np.testing.assert_allclose(previous["sesgo_mediana"], 10.0, atol=0.05)
    np.testing.assert_allclose(previous["sesgo_total"], 100 * 0.1 / 0.9, atol=0.05)
    # Con el origen en el mismo año que el bloque, la referencia reciente no tiene sesgo; con 273 días de
    # antelación, el origen de la mayoría de los bloques cae en el primer año y arrastra su nivel.
    assert abs(table.loc[("semana", 0, "reciente"), "sesgo_mediana"]) < 0.5
    assert table.loc[("mes", 273, "reciente"), "sesgo_mediana"] > 5


def test_blocks_with_estimated_cl_are_not_evaluated():
    panel = one_kwh_per_day_panel()
    table = evaluate_blocks(panel, VALIDATION, energy_scale(panel, VALIDATION), leads=[0])
    # 366 días en el año evaluado: 360 semanas posibles, de las que 7 incluyen el día con CL estimado
    assert table.loc[("semana", 0, "reciente"), "bloques"] == 360 - 7
