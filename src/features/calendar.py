"""Calendario de Sídney para los modelos de consumo.

Aplica las reglas de docs/modelado/decisiones.md (sección 6):

- La hora local es la de **inicio** de cada intervalo. timestamp_utc marca el final de la hora,
  así que se resta una hora antes de pasar a Australia/Sydney, que ya aplica el horario de verano.
- La hora estándar es la misma hora de inicio en UTC+10 todo el año, sin horario de verano.
- Festivos de Nueva Gales del Sur según la librería holidays, con el 28 de diciembre de 2010
  añadido y el Bank Holiday del 2 de agosto de 2010 quitado.
- Navidad: del 23 de diciembre al 6 de enero.

day_calendar describe cada día local y hour_calendar, cada hora.
"""
import holidays
import numpy as np
import pandas as pd

LOCAL_TZ = "Australia/Sydney"
STANDARD_UTC_OFFSET = pd.Timedelta(hours=10)

# Festivo por proclamación que la librería no incluye (forecasting_eda.ipynb, sección 0.3)
HOLIDAYS_ADDED = {pd.Timestamp("2010-12-28"): "Additional Day"}
# Bank Holiday: solo cierran los bancos y se consume como un laborable (sección 3.2)
HOLIDAYS_REMOVED = [pd.Timestamp("2010-08-02")]

# Del 23 de diciembre al 6 de enero, ambos incluidos (sección 3.2)
CHRISTMAS_FIRST = (12, 23)
CHRISTMAS_LAST = (1, 6)

SEASONS = {12: "verano", 1: "verano", 2: "verano", 3: "otoño", 4: "otoño", 5: "otoño",
           6: "invierno", 7: "invierno", 8: "invierno", 9: "primavera", 10: "primavera", 11: "primavera"}
SEASON_ORDER = ["verano", "otoño", "invierno", "primavera"]
DAY_TYPES = ["laborable", "sábado", "domingo", "festivo"]


def _utc_index(timestamp_utc):
    """Convierte una Series o un índice de marcas con zona horaria en un DatetimeIndex en UTC."""
    index = pd.DatetimeIndex(timestamp_utc)
    if index.tz is None:
        raise ValueError("Las marcas deben tener zona horaria; se esperan marcas UTC")
    return index.tz_convert("UTC")


def hour_start_local(timestamp_utc):
    """Inicio de cada hora en hora local de Sídney, a partir de la marca UTC de su final."""
    return (_utc_index(timestamp_utc) - pd.Timedelta(hours=1)).tz_convert(LOCAL_TZ)


def local_date(timestamp_utc):
    """Día local, sin hora ni zona, en que empieza cada hora."""
    return hour_start_local(timestamp_utc).tz_localize(None).normalize()


def standard_hour(timestamp_utc):
    """Hora de inicio en UTC+10 todo el año (0 a 23), sin horario de verano."""
    start = _utc_index(timestamp_utc) - pd.Timedelta(hours=1) + STANDARD_UTC_OFFSET
    return np.asarray(start.hour, dtype="int8")


def nsw_holidays(first_day, last_day):
    """Festivos de NSW entre dos fechas, ambas incluidas, como Series fecha -> nombre."""
    first_day, last_day = pd.Timestamp(first_day), pd.Timestamp(last_day)
    library = holidays.Australia(subdiv="NSW", years=range(first_day.year, last_day.year + 1))
    table = pd.Series({pd.Timestamp(day): name for day, name in library.items()}, dtype="object")
    for day, name in HOLIDAYS_ADDED.items():
        table[day] = name
    table = table.drop(HOLIDAYS_REMOVED, errors="ignore").sort_index()
    return table.loc[first_day:last_day].rename("festivo")


def is_christmas(dates):
    """Marca los días entre el 23 de diciembre y el 6 de enero, ambos incluidos."""
    dates = pd.DatetimeIndex(dates)
    month_day = dates.month * 100 + dates.day
    first = CHRISTMAS_FIRST[0] * 100 + CHRISTMAS_FIRST[1]
    last = CHRISTMAS_LAST[0] * 100 + CHRISTMAS_LAST[1]
    return np.asarray((month_day >= first) | (month_day <= last))


def day_calendar(dates):
    """Una fila por día local, indexada por fecha_local, con las variables de calendario.

    - dia_semana: 0 (lunes) a 6 (domingo).
    - festivo: el día es festivo en NSW.
    - navidad: el día está entre el 23 de diciembre y el 6 de enero.
    - laborable: de lunes a viernes, no festivo y fuera de Navidad. Es el tipo de día de la
      climatología de referencia.
    - tipo_dia: laborable, sábado, domingo o festivo. Un festivo en fin de semana cuenta como
      festivo. Es el segmento de evaluación.
    - estacion: verano (diciembre a febrero), otoño, invierno o primavera.
    """
    dates = pd.DatetimeIndex(pd.unique(pd.DatetimeIndex(dates).normalize())).sort_values()
    if dates.tz is not None:
        raise ValueError("Las fechas deben ser días locales sin zona horaria")
    if dates.empty:
        raise ValueError("No hay fechas")

    day_of_week = np.asarray(dates.dayofweek, dtype="int8")
    holiday = np.asarray(dates.isin(nsw_holidays(dates.min(), dates.max()).index))
    christmas = is_christmas(dates)
    day_type = np.select([holiday, day_of_week == 5, day_of_week == 6], ["festivo", "sábado", "domingo"],
                         default="laborable")
    return pd.DataFrame({
        "dia_semana": day_of_week,
        "festivo": holiday,
        "navidad": christmas,
        "laborable": (day_of_week < 5) & ~holiday & ~christmas,
        "tipo_dia": pd.Categorical(day_type, categories=DAY_TYPES),
        "estacion": pd.Categorical(dates.month.map(SEASONS), categories=SEASON_ORDER),
    }, index=pd.Index(dates, name="fecha_local"))


def hour_calendar(timestamp_utc):
    """Una fila por hora con su fecha y hora locales de inicio, la hora estándar y el calendario del día.

    Si timestamp_utc es una Series, el resultado conserva su índice para poder unirlo con join.
    """
    index = timestamp_utc.index if isinstance(timestamp_utc, pd.Series) else None
    start = hour_start_local(timestamp_utc)
    dates = start.tz_localize(None).normalize()
    days = day_calendar(dates).reindex(dates)
    hours = pd.DataFrame({
        "fecha_local": dates,
        "hora_local": np.asarray(start.hour, dtype="int8"),
        "hora_estandar": standard_hour(timestamp_utc),
    })
    hours = pd.concat([hours, days.reset_index(drop=True)], axis=1)
    if index is not None:
        hours.index = index
    return hours
