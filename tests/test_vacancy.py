import numpy as np
import pandas as pd
import pytest

from src.features.calendar import local_date
from src.features.vacancy import flag_vacant_days, typical_hour
from tests.conftest import hours_between

FIRST_DAY, LAST_DAY = pd.Timestamp("2011-01-01"), pd.Timestamp("2011-01-30")


def household(customer, low_days, missing_days=(), timer_days=()):
    """Un hogar con GC de 1 kWh por hora, 0,1 kWh en los días bajos y sin filas en los días que faltan.

    En los días con temporizador, tres horas siguen consumiendo 2 kWh aunque el día sea bajo.
    """
    stamps = hours_between(FIRST_DAY, LAST_DAY)
    days = local_date(stamps)
    gc = np.where(days.isin(pd.to_datetime(list(low_days))), 0.1, 1.0)
    timer = days.isin(pd.to_datetime(list(timer_days))) & np.isin(np.arange(len(stamps)) % 24, [5, 6, 7])
    gc = np.where(timer, 2.0, gc)
    frame = pd.DataFrame({"customer": customer, "timestamp_utc": stamps, "gc_kwh": gc})
    return frame.loc[~days.isin(pd.to_datetime(list(missing_days)))]


def flagged_days(data):
    flags = flag_vacant_days(typical_hour(data), reference_first_day=FIRST_DAY, reference_last_day=LAST_DAY)
    return {(customer, day.strftime("%m-%d")) for customer, day in flags[flags].index}


def test_only_runs_of_three_days_or_more_are_flagged():
    data = household(1, low_days=["2011-01-10", "2011-01-11", "2011-01-20", "2011-01-21", "2011-01-22"])
    assert flagged_days(data) == {(1, "01-20"), (1, "01-21"), (1, "01-22")}


def test_scheduled_loads_do_not_hide_an_empty_house():
    data = household(1, low_days=["2011-01-20", "2011-01-21", "2011-01-22"], timer_days=["2011-01-21"])
    assert flagged_days(data) == {(1, "01-20"), (1, "01-21"), (1, "01-22")}


def test_a_missing_day_breaks_the_run():
    data = pd.concat([
        household(1, low_days=["2011-01-10", "2011-01-11", "2011-01-13"], missing_days=["2011-01-12"]),
        household(2, low_days=["2011-01-10", "2011-01-11", "2011-01-12"]),
    ])
    assert flagged_days(data) == {(2, "01-10"), (2, "01-11"), (2, "01-12")}


def test_typical_hour_needs_gc():
    with pytest.raises(ValueError):
        typical_hour(pd.DataFrame({"customer": [1], "timestamp_utc": [pd.Timestamp("2011-01-01", tz="UTC")]}))
