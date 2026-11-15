"""Preprocesamiento de los tres archivos de Ausgrid Solar Home Electricity Data.

Aplica los cambios definidos en notebooks/ausgrid_exploration.ipynb, en este orden:

1. load_ausgrid_file: lee el CSV, comprueba su huella y elimina Row Quality.
2. parse_dates: convierte la fecha de texto con el formato de cada archivo.
3. validate_ausgrid: repite los controles de calidad del cuaderno.
4. estimate_missing_cl: rellena los días sin CL con el mismo día del año anterior.
5. find_pv_issues: localiza los problemas de GG (capacidad y días desplazados).
6. wide_to_long: pasa las 48 columnas de media hora a una fila por intervalo.
7. build_utc_timestamps: resuelve los cambios de horario y pasa a UTC.
8. pivot_categories: pasa GC, CL y GG a columnas.
9. add_total_demand: calcula el consumo total GC + CL.
10. flag_pv_issues: marca la generación no fiable.
11. aggregate_to_hourly: suma las medias horas en horas UTC.
12. consolidate_periods: une los tres años en una sola tabla.

prepare_ausgrid aplica todos los pasos. Ejecutar como módulo guarda el resultado:

    python -m src.preprocessing.ausgrid
"""
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

LOCAL_TZ = "Australia/Sydney"

# Archivo, formato de la fecha y huella registrada en docs/data/MANIFEST.md
AUSGRID_FILES = {
    "2010-2011": ("ausgrid_2010_2011.csv", "%d-%b-%y",
                  "2fc1f615e22fbd8ec350cdb19f7465d3a038453fc2ffd19473ef1bd38fd28289"),
    "2011-2012": ("ausgrid_2011_2012.csv", "%d/%m/%Y",
                  "a7d6abd1369311a5566e00d249141fd8aec28e9faba0bc928788607d961fc8c8"),
    "2012-2013": ("ausgrid_2012_2013.csv", "%d/%m/%Y",
                  "e4be46b3c9991c65735a9545319a2f1c33be8e639c75a17a88e0323a8e5098be"),
}

# Columnas de media hora, cada una etiquetada con el final del intervalo; 0:00 es la medianoche siguiente.
INTERVAL_COLUMNS = [f"{m // 60}:{m % 60:02d}" for m in range(30, 24 * 60, 30)] + ["0:00"]
INTERVAL_END_MINUTES = dict(zip(INTERVAL_COLUMNS, range(30, 24 * 60 + 1, 30)))
ID_COLUMNS = ["Customer", "Generator Capacity", "Postcode", "Consumption Category", "date"]
KEY = ["Customer", "date", "Consumption Category"]

# Intervalos de 02:00 a 03:00 afectados por los cambios de horario.
DST_SLOTS = ["2:30", "3:00"]

# Umbrales de la revisión de GG (secciones 11 y 12 del cuaderno).
OVER_CAPACITY_RATIO = 1.2
SHIFTED_SHARE = 0.2           # fracción de la energía del día entre las 00:00 y las 05:00
SHIFTED_MIN_DAILY_KWH = 0.5

OUTPUT_COLUMNS = [
    "customer", "timestamp_utc", "source_period", "generator_capacity_kwp", "postcode",
    "gc_kwh", "cl_kwh", "gg_kwh", "demand_kwh",
    "has_cl", "cl_estimated", "gg_unreliable",
]


# ---------------------------------------------------------------------------
# 1-3. Lectura, fechas y validación
# ---------------------------------------------------------------------------

def load_ausgrid_file(path, expected_sha256, period):
    """Lee un CSV anual, comprueba huella y columnas, elimina Row Quality y añade source_period.

    La fecha se deja como texto; la convierte parse_dates.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")
    file_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    if file_sha256 != expected_sha256:
        raise ValueError(f"La huella SHA-256 de {path.name} no coincide con el manifiesto: {file_sha256}")

    data = pd.read_csv(path, skiprows=1, low_memory=False)  # la primera línea es un título
    expected = ID_COLUMNS + INTERVAL_COLUMNS
    missing = set(expected) - set(data.columns)
    extra = set(data.columns) - set(expected) - {"Row Quality"}
    if missing or extra:
        raise ValueError(f"{path.name}: columnas inesperadas. Faltan: {missing}. Sobran: {extra}")

    data = data.drop(columns="Row Quality", errors="ignore")
    data["source_period"] = period
    return data


def parse_dates(data, date_format):
    """Convierte date de texto a fecha con el formato del archivo y comprueba el año."""
    parsed = pd.to_datetime(data["date"], format=date_format, errors="coerce")
    unparsed = int(parsed.isna().sum())
    if unparsed:
        raise ValueError(f"{unparsed} fechas no se pueden interpretar con el formato {date_format}")

    start_year = int(data["source_period"].iloc[0][:4])
    first_day = pd.Timestamp(f"{start_year}-07-01")
    last_day = pd.Timestamp(f"{start_year + 1}-06-30")
    outside = int((~parsed.between(first_day, last_day)).sum())
    if outside:
        raise ValueError(f"{outside} fechas quedan fuera del período {first_day.date()} a {last_day.date()}")

    data = data.copy()
    data["date"] = parsed
    return data


def validate_ausgrid(data):
    """Comprueba duplicados, celdas vacías, negativos y datos fijos del cliente. No modifica los datos."""
    errors = []
    duplicated = int(data.duplicated(subset=KEY).sum())
    if duplicated:
        errors.append(f"{duplicated} claves cliente + fecha + categoría repetidas")
    values = data[INTERVAL_COLUMNS].to_numpy(dtype=float)
    if np.isnan(values).any():
        errors.append(f"{int(np.isnan(values).sum())} celdas de energía vacías")
    if (values < 0).any():
        errors.append(f"{int((values < 0).sum())} valores de energía negativos")
    per_customer = data.groupby("Customer")[["Generator Capacity", "Postcode"]].nunique()
    if (per_customer > 1).any().any():
        errors.append("hay clientes con más de una capacidad o código postal")
    unknown = set(data["Consumption Category"]) - {"GC", "CL", "GG"}
    if unknown:
        errors.append(f"categorías desconocidas: {unknown}")

    if errors:
        period = data["source_period"].iloc[0]
        raise ValueError(f"Ausgrid {period} no supera la validación: " + "; ".join(errors))
    return data


# ---------------------------------------------------------------------------
# 4-5. Correcciones y revisiones sobre los archivos anuales
# ---------------------------------------------------------------------------

def estimate_missing_cl(tables):
    """Crea las filas CL que faltan copiando el mismo cliente y fecha del año anterior.

    Solo se estima a los clientes que tienen carga controlada en el año con algún valor mayor
    que 0; el cliente 27, cuyo CL vale siempre 0, no se estima. Si el año anterior tampoco
    tiene ese día, la fila no se crea. Las filas nuevas llevan cl_estimated = True.
    """
    periods = list(tables)
    result = {}
    for position, period in enumerate(periods):
        data = tables[period].copy()
        data["cl_estimated"] = False
        if position == 0:
            result[period] = data
            continue

        gc = data.loc[data["Consumption Category"].eq("GC"), ["Customer", "date"]]
        cl = data.loc[data["Consumption Category"].eq("CL")]
        uses_cl = cl.groupby("Customer")[INTERVAL_COLUMNS].sum().sum(axis=1).gt(0)
        cl_customers = uses_cl[uses_cl].index

        expected = gc.loc[gc["Customer"].isin(cl_customers)]
        missing = expected.merge(cl[["Customer", "date"]], how="left", indicator=True)
        missing = missing.loc[missing["_merge"].eq("left_only"), ["Customer", "date"]]
        if missing.empty:
            result[period] = data
            continue

        previous = tables[periods[position - 1]]
        previous_cl = previous.loc[previous["Consumption Category"].eq("CL"), ["Customer", "date", *INTERVAL_COLUMNS]]
        missing["previous_date"] = missing["date"] - pd.DateOffset(years=1)
        copied = missing.merge(
            previous_cl.rename(columns={"date": "previous_date"}),
            on=["Customer", "previous_date"],
            how="inner",
        )
        metadata = data.drop_duplicates("Customer").set_index("Customer")[["Generator Capacity", "Postcode"]]
        copied = copied.join(metadata, on="Customer")
        copied["Consumption Category"] = "CL"
        copied["source_period"] = period
        copied["cl_estimated"] = True
        copied = copied[data.columns]

        result[period] = pd.concat([data, copied], ignore_index=True)
    return result


def find_pv_issues(tables):
    """Devuelve los clientes con GG > 1,2 × capacidad y los días con generación desplazada.

    - Capacidad: alguna media hora con GG mayor que 1,2 × capacidad × 0,5 h en cualquier año.
    - Desplazamiento: más del 20 % de la energía del día entre las 00:00 y las 05:00.
    """
    over_capacity = set()
    shifted_days = []
    early_columns = INTERVAL_COLUMNS[:10]  # intervalos que terminan entre las 00:30 y las 05:00
    for data in tables.values():
        gg = data.loc[data["Consumption Category"].eq("GG")]
        values = gg[INTERVAL_COLUMNS].to_numpy(dtype=float)
        ratio = values / (gg["Generator Capacity"].to_numpy()[:, None] * 0.5)
        over_capacity |= set(gg.loc[(ratio > OVER_CAPACITY_RATIO).any(axis=1), "Customer"])

        daily = values.sum(axis=1)
        early = gg[early_columns].to_numpy(dtype=float).sum(axis=1)
        is_shifted = (early > SHIFTED_SHARE * daily) & (daily > SHIFTED_MIN_DAILY_KWH)
        shifted_days.append(gg.loc[is_shifted, ["Customer", "date"]])
    shifted = pd.concat(shifted_days, ignore_index=True)
    return sorted(int(c) for c in over_capacity), shifted


# ---------------------------------------------------------------------------
# 6-11. Transformación de cada año
# ---------------------------------------------------------------------------

def wide_to_long(data):
    """Pasa las 48 columnas a una fila por cliente, categoría e intervalo.

    local_end es la hora local (sin zona) del final del intervalo; 0:00 cae en el día siguiente.
    La columna date se conserva como el día del archivo al que pertenece la fila.
    """
    id_vars = ["Customer", "Generator Capacity", "Postcode", "Consumption Category", "date",
               "source_period", "cl_estimated"]
    long = data.melt(id_vars=id_vars, value_vars=INTERVAL_COLUMNS, var_name="slot", value_name="energy_kwh")
    minutes = long["slot"].map(INTERVAL_END_MINUTES)
    long["local_end"] = long["date"] + pd.to_timedelta(minutes, unit="m")
    long["energy_kwh"] = long["energy_kwh"].astype("float64")
    return long


def _dst_change_days(dates):
    """Clasifica los días de cambio de horario: 'start' (adelanta) o 'end' (atrasa)."""
    days = pd.DatetimeIndex(sorted(dates.unique()))
    noon = (days + pd.Timedelta(hours=12)).tz_localize(LOCAL_TZ)
    previous_noon = (days - pd.Timedelta(hours=12)).tz_localize(LOCAL_TZ)
    offset = np.array([t.utcoffset() for t in noon])
    previous_offset = np.array([t.utcoffset() for t in previous_noon])
    changes = {}
    for day, now, before in zip(days, offset, previous_offset):
        if now > before:
            changes[day] = "start"
        elif now < before:
            changes[day] = "end"
    return changes


def build_utc_timestamps(long):
    """Resuelve los días de cambio de horario y añade timestamp_utc (final del intervalo).

    - Inicio del horario de verano: los intervalos de 02:00 a 03:00 no existen y valen 0; se eliminan.
    - Fin del horario de verano: los intervalos de 02:00 a 03:00 suman las dos pasadas de esa
      hora; cada valor se reparte a partes iguales entre la primera pasada (UTC+11) y la segunda (UTC+10).
    Comprueba que la energía total no cambie.
    """
    energy_before = long.groupby("Consumption Category")["energy_kwh"].sum()
    changes = _dst_change_days(long["date"])
    start_days = [day for day, kind in changes.items() if kind == "start"]
    end_days = [day for day, kind in changes.items() if kind == "end"]

    in_dst_slot = long["slot"].isin(DST_SLOTS)
    nonexistent = in_dst_slot & long["date"].isin(start_days)
    if long.loc[nonexistent, "energy_kwh"].abs().sum() > 0:
        raise ValueError("Hay energía distinta de cero en la hora que no existe al empezar el horario de verano")

    repeated = in_dst_slot & long["date"].isin(end_days)
    regular = long.loc[~nonexistent & ~repeated].copy()
    # El intervalo que termina a las 02:00 del día de inicio acaba justo en el salto de reloj:
    # 02:00 en hora estándar es el mismo instante que 03:00 en horario de verano, así que se
    # desplaza hacia adelante. Las 02:00 del día de fin es ambigua y corresponde a la primera
    # pasada (horario de verano), por eso ambiguous = True.
    regular["timestamp_utc"] = (
        regular["local_end"]
        .dt.tz_localize(LOCAL_TZ, ambiguous=np.ones(len(regular), dtype=bool), nonexistent="shift_forward")
        .dt.tz_convert("UTC")
    )

    halves = []
    for offset_hours in (11, 10):  # primera pasada en horario de verano, segunda en horario estándar
        half = long.loc[repeated].copy()
        half["energy_kwh"] = half["energy_kwh"] / 2
        half["timestamp_utc"] = (half["local_end"] - pd.Timedelta(hours=offset_hours)).dt.tz_localize("UTC")
        halves.append(half)

    result = pd.concat([regular, *halves], ignore_index=True)
    energy_after = result.groupby("Consumption Category")["energy_kwh"].sum()
    if not np.allclose(energy_before, energy_after.reindex(energy_before.index), rtol=0, atol=1e-6):
        raise ValueError("La energía cambió al construir las marcas UTC")
    return result


def pivot_categories(long):
    """Pasa GC, CL y GG a columnas, con una fila por cliente e intervalo UTC."""
    index = ["Customer", "timestamp_utc"]
    wide = long.set_index([*index, "Consumption Category"])["energy_kwh"].unstack("Consumption Category")
    wide = wide.reindex(columns=["GC", "CL", "GG"])
    wide.columns = ["gc_kwh", "cl_kwh", "gg_kwh"]

    cl_estimated = (
        long.loc[long["Consumption Category"].eq("CL")]
        .set_index(index)["cl_estimated"]
    )
    info = long.drop_duplicates(index).set_index(index)[
        ["Generator Capacity", "Postcode", "source_period", "date"]
    ]
    wide = wide.join(info).join(cl_estimated)
    wide["cl_estimated"] = wide["cl_estimated"].fillna(False).astype(bool)
    wide = wide.reset_index().rename(columns={
        "Customer": "customer",
        "Generator Capacity": "generator_capacity_kwp",
        "Postcode": "postcode",
    })
    if wide.duplicated(["customer", "timestamp_utc"]).any():
        raise ValueError("Claves cliente + marca UTC repetidas después de pivotar")
    return wide


def add_total_demand(wide):
    """Calcula demand_kwh = GC + CL y la marca has_cl.

    has_cl es True si el cliente tiene CL con algún valor mayor que 0 en el año. Si no, la
    demanda es GC (caso de los clientes 27, 37 y 281). Si un cliente con carga controlada no
    tiene CL en algún intervalo, después de estimar los días que faltan, detiene el proceso.
    """
    wide = wide.copy()
    wide["has_cl"] = wide.groupby("customer")["cl_kwh"].transform(lambda values: values.fillna(0).gt(0).any())
    cl_missing = int((wide["has_cl"] & wide["cl_kwh"].isna()).sum())
    if cl_missing:
        raise ValueError(f"{cl_missing} intervalos sin CL en clientes con carga controlada")
    wide["demand_kwh"] = np.where(wide["has_cl"], wide["gc_kwh"] + wide["cl_kwh"], wide["gc_kwh"])
    return wide


def flag_pv_issues(wide, over_capacity_customers, shifted_days):
    """Añade gg_unreliable a los clientes por encima de la capacidad y a los días desplazados.

    No cambia los valores de GG.
    """
    wide = wide.copy()
    shifted_keys = pd.MultiIndex.from_frame(shifted_days.rename(columns={"Customer": "customer"}))
    row_keys = pd.MultiIndex.from_frame(wide[["customer", "date"]])
    wide["gg_unreliable"] = wide["customer"].isin(over_capacity_customers) | row_keys.isin(shifted_keys)
    return wide


def aggregate_to_hourly(wide):
    """Suma las dos medias horas de cada hora UTC, etiquetada con su final.

    Si a alguna hora le falta una de sus dos medias horas, detiene el proceso. Comprueba que la
    energía total no cambie.
    """
    wide = wide.copy()
    wide["hour_utc"] = wide["timestamp_utc"].dt.ceil("h")
    grouped = wide.groupby(["customer", "hour_utc"], sort=True)
    hourly = grouped.agg(
        source_period=("source_period", "first"),
        generator_capacity_kwp=("generator_capacity_kwp", "first"),
        postcode=("postcode", "first"),
        half_hours=("timestamp_utc", "size"),
        has_cl=("has_cl", "first"),
        cl_estimated=("cl_estimated", "any"),
        gg_unreliable=("gg_unreliable", "any"),
    )
    incomplete = int(hourly.pop("half_hours").ne(2).sum())
    if incomplete:
        raise ValueError(f"{incomplete} horas no tienen exactamente dos medias horas")
    for column in ("gc_kwh", "cl_kwh", "gg_kwh", "demand_kwh"):
        hourly[column] = grouped[column].sum(min_count=1)

    for column in ("gc_kwh", "cl_kwh", "gg_kwh"):
        if not np.isclose(wide[column].sum(), hourly[column].sum(), rtol=0, atol=1e-6):
            raise ValueError(f"La energía de {column} cambió al agregar a horas")

    hourly = hourly.reset_index().rename(columns={"hour_utc": "timestamp_utc"})
    return hourly[OUTPUT_COLUMNS]


def consolidate_periods(hourly_tables):
    """Une los tres años y comprueba que la clave cliente + marca UTC sea única."""
    data = pd.concat(hourly_tables, ignore_index=True)
    data = data.sort_values(["customer", "timestamp_utc"], ignore_index=True)
    duplicated = int(data.duplicated(["customer", "timestamp_utc"]).sum())
    if duplicated:
        raise ValueError(f"{duplicated} claves cliente + marca UTC repetidas al unir los años")
    data["source_period"] = data["source_period"].astype("category")
    data["customer"] = data["customer"].astype("int16")
    data["postcode"] = data["postcode"].astype("int16")
    return data


# ---------------------------------------------------------------------------
# Proceso completo
# ---------------------------------------------------------------------------

def prepare_ausgrid(raw_dir, verbose=True):
    """Aplica todas las funciones a los tres archivos y devuelve la tabla horaria consolidada."""
    raw_dir = Path(raw_dir)
    log = print if verbose else (lambda *args, **kwargs: None)

    tables = {}
    for period, (file_name, date_format, expected_sha256) in AUSGRID_FILES.items():
        data = load_ausgrid_file(raw_dir / file_name, expected_sha256, period)
        data = parse_dates(data, date_format)
        tables[period] = validate_ausgrid(data)
        log(f"{period}: {len(data):,} filas leídas y validadas")

    tables = estimate_missing_cl(tables)
    estimated = sum(int(t["cl_estimated"].sum()) for t in tables.values())
    log(f"Filas CL estimadas con el año anterior: {estimated}")

    over_capacity, shifted_days = find_pv_issues(tables)
    log(f"Clientes con GG por encima de {OVER_CAPACITY_RATIO} × capacidad: {over_capacity}")
    log(f"Días con generación desplazada: {len(shifted_days)} "
        f"(clientes {sorted(int(c) for c in shifted_days['Customer'].unique())})")

    hourly_tables = []
    for period, data in tables.items():
        long = wide_to_long(data)
        long = build_utc_timestamps(long)
        wide = pivot_categories(long)
        del long
        wide = add_total_demand(wide)
        wide = flag_pv_issues(wide, over_capacity, shifted_days)
        hourly = aggregate_to_hourly(wide)
        del wide
        hourly_tables.append(hourly)
        log(f"{period}: {len(hourly):,} horas de cliente")

    return consolidate_periods(hourly_tables)


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    output_path = project_root / "data" / "processed" / "ausgrid_processed.parquet"
    ausgrid = prepare_ausgrid(project_root / "data" / "raw")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ausgrid.to_parquet(output_path, index=False)
    print(f"Guardado: {output_path} ({len(ausgrid):,} filas, {ausgrid.shape[1]} columnas)")
