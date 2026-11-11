# Gaps in the data and how they are handled — task 1

Differences between what the project needs and what the selected datasets
provide. Each gap states what is missing, how it is handled, and the expected
magnitude. Structural gaps are inherent to the problem (the data will never
contain a battery). Limitation gaps are documented and accepted.
Preprocessing gaps must be resolved before any model is trained.

## Summary

| # | Gap | Type | Magnitude |
|---|---|---|---|
| G1 | Battery absent from data | Simulation | Structural |
| G2 | Censoring by battery depletion | Simulation | Structural |
| G3 | PV potential reference | Interpretation | Small |
| G4 | Inverter self-consumption | Simulation | ~5–10 % of daily energy |
| G5 | DST not encoded in Ausgrid | Preprocessing | 1 h offset, ~6 months/year |
| G6 | `0:00` column belongs to next day | Preprocessing | 30 min shift if mishandled |
| G7 | Date format differs per file | Preprocessing | Parsing error if ignored |
| G8 | Non-tropical climate (NSW) | Limitation | Qualitative |
| G9 | No historical weather forecast for 2010–2013 | Methodology | Underestimates forecast error |
| G10 | Week / month horizon scenarios | Methodology | Structural |
| G11 | Demand–PV coherence in Monte Carlo | Methodology | Underestimates P(deficit) |
| G12 | Single weather point for all customers | Assumption | Small at hourly scale |
| G13 | Controlled load (`CL`) treatment | Preprocessing | 10–15 % demand if dropped |

## What is *not* a gap

Verified during dataset selection: no missing values, no negative values, no
`NA` rows, no outliers of concern, no censoring in the demand data
(customers are grid-connected, demand is latent and fully observed). The
dataset is unusually clean; the gaps below are about what it does not
contain, not about data quality.

---

## G1 — Battery absent from data

Ausgrid has no battery, SOC, charge/discharge power, DoD or round-trip
efficiency. The battery is simulated from an initial SOC and capacity by
integrating the energy balance with simulated demand and PV as inputs.
Parameters (efficiencies, C-rate, DoD, capacity) are scenario parameters, not
fitted to data, and are varied in the Monte Carlo.

**Magnitude:** structural — without a simulated battery there is no autonomy
estimate. Sensitivity to battery parameters should be reported as a range.

## G2 — Censoring by battery depletion

In a real isolated system, when the battery reaches its lower limit the load
is disconnected and recorded consumption drops to zero while demand
continues. Ausgrid does not have this. In the training data there is nothing
to do: the demand is latent and complete, which is a strength of the dataset.
In the isolated-system simulation, censoring is injected naturally by the
battery model: when `E` reaches `E_min`, demand is counted as unserved until
generation recovers.

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

Ausgrid covers a temperate climate; the project context is tropical. The
demand model's performance in tropical conditions is unknown and not claimed.
The PV + battery simulation framework is transferable, but the autonomy
numbers are specific to NSW. If tropical validation is required, the only
honest path is a real tropical dataset; generating a synthetic tropical
dataset from Ausgrid would be an extrapolation of a temperate-trained model
with no ground truth.

**Magnitude:** qualitative — affects external validity, not internal
validity. Documented in the final report.

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

---

## Cross-cutting notes

- **DST reconstruction (G5)** is the single most likely source of subtle
  bugs. Test it on both transition days before any model uses the reshaped
  data; a regression test asserting the expected number of half-hours per
  year is recommended.
- **`0:00` re-stamping (G6)** and **DST (G5)** interact: re-stamping must
  happen before the UTC conversion, otherwise the day boundary is off by
  30 min twice a year.
- **`CL` inclusion (G13)** must be decided before the EDA, otherwise the
  baseline is computed on the wrong demand series.
- The demand series is latent and complete; **no imputation is needed** at
  any point.