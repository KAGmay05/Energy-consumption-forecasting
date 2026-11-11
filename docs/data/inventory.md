## Candidate 1 — Ausgrid Solar Home Electricity Data

| Field | Value |
|---|---|
| Institution | Ausgrid (NSW electricity distributor, Australia) |
| Country | Australia (NSW) |
| Period | 2010-07-01 to 2013-06-30 (3 years) |
| Resolution | 30 min (48 half-hour columns per row) |
| Number of installations | 300 |
| Consumption available | yes — `GC` (general) + `CL` (controlled load, ~46% of customer-days) |
| PV measured per installation | yes — `GG` (gross-metered generation, measured) |
| PV installed capacity available | yes — `Generator Capacity` in kWp (mean 1.67, median 1.50, range 1.0–9.99) |
| Location available | yes — `Postcode` (100 unique postcodes, NSW) |
| License | CC-BY 3.0 Australia (verified in mirror README, originally Ausgrid 2014) |
| Access | open download from mirror (original Ausgrid page offline; metadata at data.gov.au) |
| Format | CSV (wide: 5 descriptive + 48 half-hour cols + `Row Quality` in 2 of 3 files) |
| Size | ~55 MB compressed; ~270k rows/file, ~808k rows total |
| Official URL | original: ausgrid.com.au (offline). Metadata: https://data.gov.au/data/en/dataset/nsw-solar-home-electricty-data. Mirror: https://pierreh.eu/downloads/Ausgrid_solar_home_data.zip |
| Consultation date | 2026-11-10 |
| Notes / discrepancies | see below |

### Verified facts

- 300 customers, 365/366/365 days per customer per file, 48 half-hours per day
  → 109,500–109,800 GC and GG rows per file, 49,719–50,735 CL rows per file.
- Zero nulls, zero negatives in half-hour columns across all three files.
- `Row Quality`: absent in 2010-11; present and all `BLANK` in 2011-12 and 2012-13.
  → No `NA` rows to impute.
- Half-hour values in kWh per 30 min, positive for both consumption and generation.
  Range: 0.000 to ~7.8 kWh/30 min.
- `Generator Capacity` consistent across files: mean 1.67 kWp.

### Discrepancies vs official PDF

- CSV header is on **line 2 (index 1)**, preceded by a banner line. Must `skiprows=1`.
- Column names in CSV differ from PDF:
    PDF: `Customer | Postcode | Generator Capacity | Consumption | Date`
    CSV: `Customer | Generator Capacity | Postcode | Consumption Category | date`
- Date format differs **between files**:
    2010-2011: `%d-%b-%y`  (e.g. `1-Jul-10`)
    2011-2012: `%d/%m/%Y`  (e.g. `1/07/2011`)
    2012-2013: `%d/%m/%Y`
- Column `0:00` corresponds to interval **23:30–0:00 of the next day** (Ausgrid quirk).
  Must be re-stamped as `date + 1 day, 00:00` during reshape.
- **DST is not encoded**: all 48 half-hour columns have identical non-null counts
  (270,304), and DST transition days (2 Oct 2011, 1 Apr 2012) have 48 non-null
  values, not 46/50. The dataset treats every day as 24 nominal hours.

### Implications for the project

- **Latent demand**: grid-connected customers → no battery-depletion censoring.
  Advantage for demand modelling; censoring is injected when simulating isolated system.
- **PV potential**: gross-metered `GG` measures total generation with no
  curtailment from a full battery → approximates PV potential well.
- **Climate**: single climate zone (temperate NSW). Does not validate the
  tropical context mentioned in the project. Documented limitation.
- **No historical forecast for 2010–2013** in Open-Meteo (starts ~2022).
  Full-chain backtesting will use ERA5 as "perfect forecast" or with
  calibrated perturbation. See `gaps.md`.
- **DST reconstruction required** before joining with UTC-based weather
  and running pvlib. See `gaps.md`.

### Sample sanity check (Customer 1, Postcode 2076, 3.78 kWp)

- 1 Jul 2010: GC profile typical of winter residential (evening peak),
  GG zero until ~13:00, peak ~1.18 kWh/30 min around midday.
  Consistent with a north-facing 3.78 kWp system in Sydney winter.