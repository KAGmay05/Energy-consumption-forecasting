"""Pliegues, orígenes y horizonte de los pronósticos (docs/modelado/decisiones.md, secciones 1, 2 y 4).

Cada día del año evaluado se pronostica desde las 00:00 hora local, el origen t0, para los 14 días
locales siguientes. El paso h cuenta horas reales desde el origen: h = 1 es la hora de 00:00 a 01:00
del primer día. El horizonte tiene 336 horas, o 335 y 337 si incluye un cambio de horario, así que
las matrices de pronóstico tienen MAX_STEPS = 337 columnas, e in_horizon marca las que pertenecen
al horizonte de cada origen.

Un par hogar-origen se evalúa solo si los 28 días locales anteriores al origen y los 14 del horizonte
tienen todas sus horas. Dentro de esos pares no se evalúan las horas con CL estimado.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.features.calendar import LOCAL_TZ, hour_start_local, local_date

HORIZON_DAYS = 14
HISTORY_DAYS = 28
MAX_STEPS = 24 * HORIZON_DAYS + 1


def local_midnight_utc(dates):
    """Marca UTC de las 00:00 hora local de cada día. En Sídney la medianoche siempre existe y es única."""
    return pd.DatetimeIndex(dates).tz_localize(LOCAL_TZ).tz_convert("UTC")


@dataclass(frozen=True)
class Fold:
    """Un pliegue: el periodo de ajuste y el año evaluado, como días locales incluidos."""
    name: str
    fit_first_day: pd.Timestamp
    fit_last_day: pd.Timestamp
    eval_first_day: pd.Timestamp
    eval_last_day: pd.Timestamp

    def origin_dates(self):
        """Día local d0 de cada origen: los del año evaluado cuyos 14 días caen dentro del año."""
        last = self.eval_last_day - pd.Timedelta(days=HORIZON_DAYS - 1)
        return pd.date_range(self.eval_first_day, last, freq="D", name="origen")

    def origins(self):
        """Marca UTC de cada origen t0: el final de la hora que termina a las 00:00 local de d0."""
        return local_midnight_utc(self.origin_dates())

    def fit_hours(self, timestamps_utc):
        """Marca las horas cuyo día local está en el periodo de ajuste."""
        dates = local_date(timestamps_utc)
        return np.asarray((dates >= self.fit_first_day) & (dates <= self.fit_last_day))


VALIDATION = Fold("validacion", pd.Timestamp("2010-07-01"), pd.Timestamp("2011-06-30"),
                  pd.Timestamp("2011-07-01"), pd.Timestamp("2012-06-30"))
TEST = Fold("test", pd.Timestamp("2010-07-01"), pd.Timestamp("2012-06-30"),
            pd.Timestamp("2012-07-01"), pd.Timestamp("2013-06-30"))
FOLDS = {fold.name: fold for fold in (VALIDATION, TEST)}


@dataclass(frozen=True)
class ForecastGrid:
    """Las horas que se pronostican desde cada origen de un pliegue.

    Las matrices tienen forma (orígenes, MAX_STEPS) y la columna j es el paso h = j + 1.
    - target_utc: final de cada hora pronosticada, datetime64 en UTC sin zona.
    - fecha_local y hora_local: día y hora locales en que empieza.
    - day: día de horizonte k, de 1 a 14, y 0 fuera del horizonte.
    - in_horizon: la hora pertenece a los 14 días del origen.
    """
    fold: Fold
    origins: pd.DatetimeIndex
    target_utc: np.ndarray
    fecha_local: np.ndarray
    hora_local: np.ndarray
    day: np.ndarray
    in_horizon: np.ndarray

    @property
    def steps(self):
        return np.arange(1, MAX_STEPS + 1)


def forecast_grid(fold):
    """Construye el ForecastGrid de un pliegue."""
    origins = fold.origins()
    steps = np.arange(1, MAX_STEPS + 1)
    target = origins.tz_convert(None).to_numpy()[:, None] + steps[None, :] * np.timedelta64(1, "h")

    start = hour_start_local(pd.DatetimeIndex(target.ravel()).tz_localize("UTC"))
    dates = start.tz_localize(None).normalize().to_numpy().reshape(target.shape)
    hours = np.asarray(start.hour, dtype="int8").reshape(target.shape)
    origin_dates = fold.origin_dates().to_numpy()
    day = (dates - origin_dates[:, None]) // np.timedelta64(1, "D") + 1
    in_horizon = (day >= 1) & (day <= HORIZON_DAYS)
    if not (day[:, 0] == 1).all() or not (hours[:, 0] == 0).all():
        raise ValueError("El primer paso de algún origen no es la hora de 00:00 a 01:00 de su día")

    return ForecastGrid(fold=fold, origins=origins, target_utc=target, fecha_local=dates, hora_local=hours,
                        day=np.where(in_horizon, day, 0).astype("int8"), in_horizon=in_horizon)


def target_positions(grid, panel):
    """Posición en el panel de cada hora pronosticada. Fuera del horizonte vale 0 y no se usa."""
    positions = np.zeros(grid.target_utc.shape, dtype="int64")
    positions[grid.in_horizon] = panel.positions(grid.target_utc[grid.in_horizon])
    return positions


def gather(panel, column, grid):
    """Valores de una columna del panel en las horas pronosticadas: (hogares, orígenes, MAX_STEPS).

    Fuera del horizonte las columnas numéricas valen NaN y las booleanas, False.
    """
    values = panel[column][:, target_positions(grid, panel)]
    values[:, ~grid.in_horizon] = False if values.dtype == bool else np.nan
    return values


def evaluable_pairs(panel, fold):
    """(hogares, orígenes): los 28 días locales anteriores al origen y los 14 del horizonte están completos."""
    origin_dates = fold.origin_dates()
    first = panel.positions(local_midnight_utc(origin_dates - pd.Timedelta(days=HISTORY_DAYS)))
    last = panel.positions(local_midnight_utc(origin_dates + pd.Timedelta(days=HORIZON_DAYS)))
    # Las horas del intervalo son las de las posiciones first + 1 a last.
    present_before = np.concatenate(
        [np.zeros((len(panel.customers), 1), dtype="int64"), np.cumsum(panel.present, axis=1)], axis=1)
    present_hours = present_before[:, last + 1] - present_before[:, first + 1]
    return present_hours == (last - first)[None, :]


def evaluation_mask(panel, grid):
    """(hogares, orígenes, MAX_STEPS): las horas que entran en las métricas.

    Una hora entra si está en el horizonte, existe en los datos, su CL no es estimado y su par
    hogar-origen es evaluable (evaluable_pairs).
    """
    if "cl_estimated" not in panel.values:
        raise ValueError("El panel necesita la columna cl_estimated para excluir esas horas")
    positions = target_positions(grid, panel)
    mask = panel.present[:, positions] & ~panel["cl_estimated"][:, positions]
    mask &= evaluable_pairs(panel, grid.fold)[:, :, None]
    mask &= grid.in_horizon[None, :, :]
    return mask
