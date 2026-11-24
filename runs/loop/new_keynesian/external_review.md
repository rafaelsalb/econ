# External review — New Keynesian QPM (R3)

**Scope.** Packet only; no code, lockbox untouched.

## 1. Identification: labels vs. estimates

The arithmetic fits the card—NKPC coefficients sum to 1.0000, Taylor constant 0.0, IS real-rate t = −4.08—but the labels outrun the estimates. The NKPC forward term is the 12-month-ahead Focus median at weight 0.605, not a one-step-ahead expectation; for h < 12 it is horizon-mismatched, and holding it fixed makes the forecast an anchor-copy. The Taylor rule responds to the same Focus series that drives the NKPC (rho = 0.966); the long-run coefficient 0.097/(1 − 0.966) = 2.85 is not robustly identified, so the Taylor-principle test is circular. The gap is HP-filtered, so IS R² = 0.871 is mechanical. Transmission is null: a permanent 1pp real-rate rise lowers the gap 0.45pp and monthly inflation 0.0037pp, ~4bp/year.

## 2. Missed or underclassified defects

| Code | Severity | Defect and evidence |
|---|---|---|
| D7 | **high** | **FX sign violation.** `dfx_1 = −0.000404` (t = −0.11); `irf.fx_to_inflation = −1.0`. `blocking_high` includes D7-sign and METHOD makes sign violations high; the critic's medium label lets the model pass. Prediction #4 fails. |
| D3 | **high** | **Lockbox/COVID contamination.** h=12 cells have `last_origin = 2019-12`, n = 120, so 12/120 targets are 2020-01..2020-12, inside the lockbox (6/120 at h=6). A COVID dummy is switched on for 2020-03..2020-12 though it is "used only when identified" and the sample ends 2019-12. Core and Selic h=12 gates are not clean. |
| D3 | **high** | **Sample mismatch.** `nobs` = 201/201/202 at 2019-12. A 2005-01 start with two lags gives 178; 201 implies ~203 raw months, start ~2003-01. The frozen `estimation_start` is violated. |
| D3 | **high** | **Gap is not one-sided.** `gap.mean = 6.0e-10`, `sd = 2.115`. A single full-sample HP cycle sums to zero exactly; a recursive one-sided gap would not. That is the signature of a two-sided HP cycle truncated at the origin—look-ahead untested by `leak_ok`. |
| D1 | **high** | **Core transmission not identified.** NKPC `gap_1 = 0.00819`, t = 1.37; stability moves it 0.00284 → 0.00819 (2.9×). Refutation #1 says an insignificant gap refutes the core channel; the critic called D1 medium "precision," but the card makes it structural. |
| D5 | **high** | **Gate leniency/benchmark duplication.** The core rule only beats RW; the model never beats Focus in the five primary cells (mean rank 2.8 vs 1.0), and h=12 RMSE 1.748 vs 1.742, MZ slope 1.637 vs 1.637. GDP rows are byte-identical to `ibc_bridge` at h=0..4 (RMSE 0.7060, 1.1582, 1.9144, 2.2426, 2.3053), so the auxiliary GDP gate tests the benchmark. Selic is gated only at h=12 (Theil 1.022, worse than RW); h=3/h=6 are 1.177/1.110. |
| D1/D5 | medium | **Taylor misspecification.** LB p = 3.2e-26, rho = 0.966, g1 = 0.097. The late-origin Selic path reaches 7.88% vs actual 2020 2.0%; h=12 bias +1.06. Target 4.0 plus r* = 4.0 imposes an 8.0% neutral rate, 350bp above the actual 4.5% Selic. |
| D5 | medium | **Missing promised tests.** No sub-sample refutation of the IS/NKPC (only two-origin before/after); no 2015-16/2018 episode scorecard; no joint MZ or DM vs Focus. The h=12 MZ slope 1.637 (p = 0.190) is far from 1; overlapping 12-month targets make the p-value fragile. |

## 3. Verdict: OVERTURN_TO_REJECT

PASS_WITH_LIMITATIONS is not defensible. The FX coefficient is wrong-signed and the diagnostics record `fx_to_inflation = −1.0`; `blocking_high` includes D7-sign and METHOD makes sign violations high, so the critic's medium label is the only thing between the model and rejection. Independently, the h=12 core and Selic gates use 2020 outcomes and a non-identified COVID dummy from the lockbox, the estimation sample is ~2 years longer than declared, and the gap is a full-sample HP cycle. These are D3-high data-contract violations, not limitations. The inflation forecasts are decent (IPCA 12m Theil 0.508/0.456), but they come from a fixed Focus anchor: the gap coefficient is insignificant (t = 1.37), IS×NKPC transmission is ~4bp/year, the model never beats Focus in the primary cells, and the GDP gate is a duplicate benchmark. With the ladder exhausted, REJECT is consistent; REVISE would need a new card, a clean real-time sample, and a non-vacuous structural gate.
