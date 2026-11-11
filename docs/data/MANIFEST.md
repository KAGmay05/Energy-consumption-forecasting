# Data manifest — task 1

All datasets used in task 1. Two sources: Ausgrid (downloaded manually from
a static mirror) and Open-Meteo ERA5 (downloaded via a script). Each file is
SHA-256-verified before being placed in `data/raw/` or `data/weather/`.

## Where the data lives

- Ausgrid CSVs: `data/raw/` (gitignored). Shared copy: `https://drive.google.com/file/d/1uF5bdWaEl-Q6VyxT9G-PVJkpbHZQEEcx/view?usp=sharing`.
- Open-Meteo parquet: `data/weather/` (gitignored). Shared copy: `https://drive.google.com/file/d/1Qde4yv6pQ_0q-lKonvf8FKOLE9zpr0bd/view?usp=sharing`.

## Reproducibility note

- **Ausgrid** is downloaded **manually** from a mirror zip. There is no
  download script. The zip is a static file; SHA-256 is the reproducibility
  guarantee.
- **Open-Meteo ERA5** is downloaded via `scripts/00_download_weather.py`.
  The parquet file is **frozen**; re-running the script may return slightly
  different values if Open-Meteo updates its ERA5 backend. The frozen file
  (SHA-256 below) is the ground truth for this project.

---

## Ausgrid — Solar Home Electricity Data

Source: https://pierreh.eu/downloads/Ausgrid_solar_home_data.zip
The zip contains the three CSVs, a PDF with the original Ausgrid notes, and
the mirror README. Only the three CSVs are used in this project.

| Canonical name | Original name in zip | SHA-256 | Rows | Verified on |
|---|---|---|---|---|
| `ausgrid_2010_2011.csv` | `Solar home 2010-2011.csv` | `2FC1F615E22FBD8EC350CDB19F7465D3A038453FC2FFD19473EF1BD38FD28289` | 269,735 | 2026-11-10 |
| `ausgrid_2011_2012.csv` | `Solar home 2011-2012.csv` | `A7D6ABD1369311A5566E00D249141FD8AEC28E9FABA0BC928788607D961FC8C8` | 270,304 | 2026-11-10 |
| `ausgrid_2012_2013.csv` | `Solar home 2012-2013.csv` | `E4BE46B3C9991C65735A9545319A2F1C33BE8E639C75A17A88E0323A8E5098BE` | 268,557 | 2026-11-10 |

### Schema (all three files)

- **Layout:** wide. Each row is one `(customer, day, consumption category)`.
- **First line of each file is a banner**, not a header. The real header is
  on **line 2 (index 1)**. Read with `skiprows=1`, or auto-detect the first
  line that starts with `Customer`.
- **Descriptive columns (5):** `Customer` (1..300), `Generator Capacity` (kWp),
  `Postcode`, `Consumption Category` (`GC` / `CL` / `GG`), `date`.
- **48 half-hour columns:** `0:30` … `23:30`, `0:00`. kWh per 30-minute
  interval, positive for both consumption and generation.
- **`Row Quality`:** present only in 2011-2012 and 2012-2013, all blank.
  Absent in 2010-2011.

### Date formats (inconsistent across files)

| File | Format | Example |
|---|---|---|
| `ausgrid_2010_2011.csv` | `%d-%b-%y` | `1-Jul-10` |
| `ausgrid_2011_2012.csv` | `%d/%m/%Y` | `1/07/2011` |
| `ausgrid_2012_2013.csv` | `%d/%m/%Y` | `1/07/2012` |

### Units and conventions

- Values are **kWh per 30 minutes**, not kW. Multiply by 2 to get average kW.
- `0:00` column = interval **23:30–0:00 of the next day**. During reshape,
  re-stamp as `D + 1 day, 00:00`.
- Timezone: local NSW (EST/EDT). **DST not encoded** — every day is 48
  nominal half-hours, including 2 Oct 2011 and 1 Apr 2012. Reconstruct UTC
  from date + `Australia/Sydney` rules. See `gaps.md`.
- No nulls, no negatives, no `NA` rows.

### License

CC-BY 3.0 Australia. Originally published by Ausgrid in 2014; metadata at
https://data.gov.au/data/en/dataset/nsw-solar-home-electricty-data.

### How to reproduce (Ausgrid)

1. Download https://pierreh.eu/downloads/Ausgrid_solar_home_data.zip
2. Extract and rename:
   - `Solar home 2010-2011.csv` → `ausgrid_2010_2011.csv`
   - `Solar home 2011-2012.csv` → `ausgrid_2011_2012.csv`
   - `Solar home 2012-2013.csv` → `ausgrid_2012_2013.csv`
3. Verify SHA-256: `Get-FileHash <file> -Algorithm SHA256` (Windows) or
   `sha256sum <file>` (Linux/macOS).
4. Place in `data/raw/`.

---

## Weather — Open-Meteo ERA5

| Canonical name | SHA-256 | Rows | Period |
|---|---|---|---|
| `era5_sydney_2010_2013.parquet` | `63e45ef341654d177c3670d109d54d344e971859fd46b799b1b7bb0133ae0f58` | 26,304 | 2010-07-01 → 2013-06-30 (hourly, UTC) |

### Parameters

| Parameter | Value |
|---|---|
| Endpoint | `https://archive-api.open-meteo.com/v1/archive` |
| Latitude | `-33.8688` (Sydney CBD) |
| Longitude | `151.2093` |
| Start / end | `2010-07-01` / `2013-06-30` |
| Timezone | `UTC` |
| Model | `era5` (explicit) |
| Variables | `temperature_2m`, `relative_humidity_2m`, `precipitation`, `cloud_cover`, `shortwave_radiation`, `direct_normal_irradiance`, `diffuse_radiation`, `wind_speed_10m`, `surface_pressure` |

### Assumptions

- **Single weather point.** All 300 Ausgrid customers share the Sydney CBD
  grid point. Ausgrid postcodes span ~150 km; at hourly resolution,
  within-region climate variation is small compared with day-to-day
  variability. Revisit if per-postcode simulations are needed.
- **ERA5 only.** Historical Forecast API is not available for 2010–2013
  (starts ~2022). Forecast and Ensemble APIs are not downloaded in task 1;
  they will be used in task 4 (Monte Carlo). See `gaps.md`.
- **All timestamps in UTC.** Do not convert to local time. DST reconstruction
  happens on the Ausgrid side, and the join with Ausgrid must be in UTC.

### How to reproduce (Weather)

1. Download `weather_task1.zip` from `https://drive.google.com/file/d/1Qde4yv6pQ_0q-lKonvf8FKOLE9zpr0bd/view?usp=sharing`, extract
   `era5_sydney_2010_2013.parquet` into `data/weather/`.
2. Verify SHA-256 with `Get-FileHash` or `sha256sum`.
3. Or re-run `python scripts/00_download_weather.py`. This will download fresh
   data from Open-Meteo, which **may differ slightly** from the frozen version.
   The frozen file is the source of truth.