import numpy as np
import pandas as pd

from src.features.calendar import day_calendar, hour_calendar, hour_start_local, local_date, nsw_holidays, standard_hour


def utc_hours(first, last):
    return pd.date_range(first, last, freq="h", tz="UTC")


def test_hour_start_is_one_hour_before_the_utc_mark():
    # La primera hora del conjunto termina a las 00:00 UTC del 1-jul-2010: 10:00 hora local, así que empieza a las 09:00
    start = hour_start_local(pd.DatetimeIndex([pd.Timestamp("2010-07-01 00:00", tz="UTC")]))
    assert start[0] == pd.Timestamp("2010-07-01 09:00", tz="Australia/Sydney")


def test_dst_days_have_23_and_25_hours():
    hours = utc_hours("2011-09-30", "2011-10-05").append(utc_hours("2012-03-29", "2012-04-04"))
    per_day = pd.Series(local_date(hours)).value_counts()
    assert per_day[pd.Timestamp("2011-10-02")] == 23  # empieza el horario de verano
    assert per_day[pd.Timestamp("2012-04-01")] == 25  # termina
    assert per_day[pd.Timestamp("2011-10-03")] == 24


def test_standard_hour_ignores_daylight_saving():
    winter = pd.DatetimeIndex([pd.Timestamp("2011-07-15 03:00", tz="UTC")])  # 13:00 local, UTC+10
    summer = pd.DatetimeIndex([pd.Timestamp("2012-01-15 03:00", tz="UTC")])  # 14:00 local, UTC+11
    assert standard_hour(winter)[0] == hour_start_local(winter).hour[0] == 12
    assert standard_hour(summer)[0] == 12
    assert hour_start_local(summer).hour[0] == 13


def test_holiday_changes():
    table = nsw_holidays("2010-07-01", "2013-06-30")
    assert pd.Timestamp("2010-12-28") in table.index  # añadido a mano
    assert pd.Timestamp("2010-08-02") not in table.index  # Bank Holiday quitado
    assert pd.Timestamp("2010-12-27") in table.index
    assert pd.Timestamp("2013-01-28") in table.index  # Australia Day trasladado al lunes
    assert len(table.loc["2012-07-01":"2013-06-30"]) == 11


def test_day_calendar():
    days = day_calendar(pd.to_datetime(["2010-08-02", "2010-12-22", "2010-12-25", "2010-12-29",
                                        "2011-01-06", "2011-01-07", "2011-02-28", "2011-03-01", "2011-03-05"]))
    row = days.loc
    assert row["2010-08-02", "tipo_dia"] == "laborable" and row["2010-08-02", "laborable"]
    assert not row["2010-12-22", "navidad"] and row["2010-12-22", "laborable"]
    assert row["2010-12-25", "tipo_dia"] == "festivo"  # sábado y festivo: cuenta como festivo
    assert row["2010-12-29", "tipo_dia"] == "laborable" and row["2010-12-29", "navidad"]
    assert not row["2010-12-29", "laborable"]  # laborable de Navidad: no laborable en la climatología
    assert row["2011-01-06", "navidad"] and not row["2011-01-07", "navidad"]
    assert row["2011-01-07", "laborable"]
    assert row["2011-02-28", "estacion"] == "verano" and row["2011-03-01", "estacion"] == "otoño"
    assert row["2011-03-05", "tipo_dia"] == "sábado"


def test_hour_calendar_keeps_the_series_index():
    stamps = pd.Series(utc_hours("2011-12-24 10:00", "2011-12-25 10:00"), index=np.arange(100, 125))
    hours = hour_calendar(stamps)
    assert list(hours.index) == list(stamps.index)
    first = hours.iloc[0]
    assert first["fecha_local"] == pd.Timestamp("2011-12-24") and first["hora_local"] == 20
    assert first["hora_estandar"] == 19
    assert hours.loc[hours["fecha_local"].eq(pd.Timestamp("2011-12-25")), "festivo"].all()
