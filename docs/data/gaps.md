# Gaps in the data and how they are handled — task 1

Differences between what the project needs and what the selected datasets
provide. Each gap states what is missing, how it is handled, and the expected
magnitude. Structural gaps are inherent to the problem (the data will never
contain a battery). Limitation gaps are documented and accepted.
Preprocessing gaps must be resolved before any model is trained.

## Summary

| # | Gap | Type | Magnitude |
|---|---|---|---|
| G1 | Battery absent from data | Simulation (task 3) | Structural |
| G2 | Censoring by battery depletion | Simulation (task 3) | Structural |
| G3 | PV potential reference | Interpretation | Small |
| G4 | Inverter self-consumption | Simulation (task 3) | ~5–10 % of daily energy |
| G5 | DST not encoded in Ausgrid | Preprocessing | 1 h offset, ~6 months/year |
| G6 | `0:00` column belongs to next day | Preprocessing | 30 min shift if mishandled |
| G7 | Date format differs per file | Preprocessing | Parsing error if ignored |
| G8 | Non-tropical climate (NSW) | Limitation | Qualitative |
| G9 | No historical weather forecast for 2010–2013 | Methodology | Underestimates forecast error |
| G10 | Week / month horizon scenarios | Methodology | Structural |
| G11 | Demand–PV coherence in Monte Carlo | Methodology | Underestimates P(deficit) |
| G12 | Single weather point for all customers | Assumption | Small at hourly scale |
| G13 | Controlled load (`CL`) treatment | Preprocessing | 10–15 % demand if dropped |
| G14 | 81 customer-days absent in 2012-2013 | Data | 0.07 % of that year |

## What is *not* a gap

Verified during dataset selection, **at the cell level**: no missing values
inside any row, no negative values, no `NA` rows in `Row Quality`, no
outliers of concern, no censoring in the demand data (customers are
grid-connected, demand is latent and fully observed).

One exception at the **row level**: 81 `(customer, day)` pairs are entirely
absent from the 2012-2013 file (see G14). This is not "missing values" within
rows; it is whole rows that do not appear. It affects 0.07 % of that year
and does not require imputation.

The dataset is unusually clean. The gaps below are about what it does not
contain, not about data quality.

---

## G1 — Battery absent from data

Ausgrid has no battery, SOC, charge/discharge power, DoD or round-trip
efficiency. The battery is simulated from an initial SOC and capacity by
integrating the energy balance with **forecasted** demand (output of the
demand model, task 2) and **forecasted** PV (output of pvlib, task 3) as
inputs. Parameters (efficiencies, C-rate, DoD, capacity) are scenario
parameters, not fitted to data, and are varied in the Monte Carlo.

**Important:** this is a **modelling step (task 3), not data preparation for
task 1.** Task 1 provides clean, verified data; the battery simulation
requires the forecasts from tasks 2 and 3, which do not yet exist. The gap is
documented here so that the assumption is not lost, but it is **not computed
in task 1**.

**Magnitude:** structural — without a simulated battery there is no autonomy
estimate. Sensitivity to battery parameters should be reported as a range.

## G2 — Censoring by battery depletion

In a real isolated system, when the battery reaches its lower limit the load
is disconnected and recorded consumption drops to zero while demand
continues. Ausgrid does not have this. In the training data there is nothing
to do: the demand is latent and complete, which is a strength of the dataset.
In the isolated-system simulation (task 3), censoring is injected naturally
by the battery model: when `E` reaches `E_min`, demand is counted as
unserved until generation recovers.

**Magnitude:** structural. Note in the report that real isolated-system
demand may also be suppressed by the user when the battery is low, which
cannot be reproduced from grid data. Known limitation, not corrected.

## G3 — PV potential reference

Ausgrid's `GG` (gross generation) is measured by a gross meter that records
total PV output independently of load. Since the system is grid-connected and
the excess is exported, there is no curtailment from a full battery, so `GG`
is very close to potential generation. Use `GG` as the reference for
validating pvlib on clear days. In the isolated-system simulation, use pvlib
output as the PV input; the battery model decides how much is actually used.

**Magnitude:** small (inverter clipping, soiling, measurement errors).
Quantify on clear days.

## G4 — Inverter self-consumption

Real inverters consume 20–50 W continuously while on, drawn from the battery
at night, not present in Ausgrid's load data. Add a constant inverter
consumption (default 30 W) to simulated demand. Scenario parameter, varied in
the Monte Carlo.

**Magnitude:** 0.5–1.5 kWh/day, 5–15 % of a typical Ausgrid daily
consumption. Material for daily autonomy; must be included.

## G5 — DST not encoded in Ausgrid

Every day is encoded as 48 nominal half-hours regardless of the actual 46 or
50 at DST transitions. Verified: all 48 columns have identical non-null
counts, and transition days have 48 non-null values. Reconstruct UTC from
date + `Australia/Sydney` rules. On the two transition days there is a 30-min
ambiguity; recommended: drop the duplicated hour at DST end, interpolate the
missing hour at DST start, and document the choice.

**Magnitude:** if unhandled, 1 h systematic misalignment with ERA5 /
Open-Meteo for ~6 months/year. Breaks pvlib solar position, lag features and
the demand–weather join. Must be handled.

## G6 — `0:00` column belongs to the next day

The last half-hour column (`0:00`) represents 23:30–0:00 of the next day, not
of the same day. During reshape, re-stamp it as `date + 1 day, 00:00 local`.

**Magnitude:** if mishandled, 30-min gap and 30-min overlap at every day
boundary. Breaks hour aggregation, lags and resampling. Must be handled.

## G7 — Date format differs per file

`ausgrid_2010_2011.csv` uses `%d-%b-%y`; the other two use `%d/%m/%Y`. Parse
each file with its own format, or use `errors='coerce'` and assert zero NaT.
Do not assume a single parser.

**Magnitude:** if mishandled, 100 % NaT for two of the three files. Must be
handled.

## G8 — Non-tropical climate (NSW)

Ausgrid covers a temperate climate. The project brief is climate-agnostic
("PV capacity + weather data → how long it lasts"), but the team context
mentions Cuba as the intended deployment. The demand model's performance in
tropical conditions is unknown and not claimed. The PV + battery simulation
framework is transferable; the autonomy numbers are specific to NSW.

**Magnitude:** qualitative — affects external validity, not internal
validity. Documented in the final report. No additional dataset is required
by the brief; if tropical validation is later requested, the only honest
path is a real tropical dataset, not a synthetic one derived from Ausgrid.

## G9 — No historical weather forecast for 2010–2013

Open-Meteo's Historical Forecast API starts ~2022; for the Ausgrid period
only ERA5 (reanalysis) is available. Options, in order of preference:

1. **ERA5 as "perfect forecast".** Simplest; reported autonomy error is a
   **lower bound** on the real error.
2. **ERA5 + calibrated perturbation.** Perturbation distribution matched to
   typical 24–72 h operational forecast error. More realistic.
3. **Report both** (1) and (2); difference quantifies how much of the
   autonomy error is due to forecast imperfection. Recommended.

**Magnitude:** the "perfect forecast" backtest underestimates the real error.

## G10 — Week / month horizon scenarios

Forecasts do not extend beyond ~15 days with useful skill; for longer
horizons only climatology is available. Generate scenarios from climatology
(analog days in multi-day blocks, or Markov chains of day types by clearness
index). The answer for these horizons is an aggregate (expected daily hours
of supply, expected days with any cut, probability of at least one depletion),
not a forecast of specific hours.

**Magnitude:** structural — the answer changes in kind, not only in
precision.

## G11 — Demand–PV coherence in Monte Carlo

Independent sampling of demand and PV breaks their correlation, mixing
clear-sky PV with cloudy-day demand and distorting deficit probabilities. Two
mechanisms: (i) Open-Meteo ensemble members for horizons ≤ 15 days, each
giving a coherent trajectory of temperature, irradiance, cloud cover and wind
fed to both the demand model and pvlib; (ii) block bootstrap of demand
residuals in 24 h blocks, not hour by hour, to preserve autocorrelation.
Sampling residuals hour by hour makes them compensate within each night and
underestimates the dispersion of autonomy.

**Magnitude:** if unhandled, probability of prolonged deficit is
underestimated. Block bootstrap is the minimum acceptable treatment.

## G12 — Single weather point for all customers

All 300 customers share one ERA5 grid point (Sydney CBD). The postcodes span
~150 km, which at ERA5 resolution covers a few cells. Accepted as an
assumption: at hourly resolution, variation between nearby NSW locations is
small compared with day-to-day variation at any one location. Per-postcode
weather would multiply data by ~100 without a clear gain. Revisit if
per-postcode simulation is needed.

**Magnitude:** small, much smaller than the error from the missing
operational forecast (G9) or the missing battery parameters (G1).

## G13 — Controlled load (`CL`) treatment

Ausgrid has three categories: `GC` (general consumption), `CL` (controlled
load, off-peak water heating, ~46 % of customer-days), `GG` (gross
generation). `CL` is real demand on a separate meter with a distinct
temporal pattern. Two options:

1. **Include `CL` in total demand** (`GC + CL`). Recommended: total
   consumption is what an isolated system must cover.
2. **Model `GC` and `CL` separately.** More accurate but doubles the
   modelling work. Revisit in task 2 if the EDA shows a very distinct and
   predictable `CL` pattern.

**Magnitude:** if `CL` is dropped, demand is underestimated by 10–15 % on
affected days, propagating directly to autonomy.

## G14 — 81 customer-days absent in 2012-2013

The 2012-2013 file contains 109,419 `GC` rows and 109,419 `GG` rows, versus
the expected 109,500 (= 300 customers × 365 days). The 2010-2011 and
2011-2012 files have exactly the expected counts (109,500 and 109,800
respectively, the latter because 2012 is a leap year). This means **81
`(customer, day)` pairs are entirely absent** from the 2012-2013 file: no
`GC` row, no `GG` row, and consequently no `CL` row for those pairs either.

This is not "missing values" inside a row (which is zero everywhere); it is
whole rows that do not appear in the file.

**How it is handled.** **Discard** those pairs, do not impute them. 81 out
of 109,500 is 0.07 % of the year; imputing them would fabricate data with no
justification and would bias any metric computed on the affected customer-
days. When reshaping wide-to-long, those pairs simply do not generate rows;
the model must tolerate the resulting gaps in the per-customer time series
(e.g. when computing lags, skip missing timestamps rather than propagate).

**Magnitude:** 0.07 % of one year in one file. No material effect on model
training or on autonomy estimation. Must be documented so that whoever
reshapes the data does not mistake the absence for a parsing bug.

**Interaction with other gaps:** G14 does not interact with G5 (DST) or G6
(`0:00`); it is an independent missingness at the row level. It is listed
last because it was discovered after the main verification.

---

## Cross-cutting notes

- **G5 (DST reconstruction)** is the single most likely source of subtle
  bugs. Test it on both transition days before any model uses the reshaped
  data; a regression test asserting the expected number of half-hours per
  year is recommended.
- **G6 (`0:00` re-stamping)** and **G5 (DST)** interact: re-stamping must
  happen before the UTC conversion, otherwise the day boundary is off by
  30 min twice a year.
- **G13 (`CL` inclusion)** must be decided before the EDA, otherwise the
  baseline is computed on the wrong demand series.
- **G14 (81 absent customer-days)** must be handled at reshape time, not at
  imputation time. Do not fill them.
- **G1–G4 are task-3 modelling steps**, not task-1 data preparation. Task 1
  ends with clean, verified data; the battery simulation starts once demand
  and PV forecasts exist.
- The demand series is latent and complete at the cell level; **no
  imputation is needed** at any point. G14 is a whole-row absence, not a
  missing value.