# Live advisory review — 2026-11-24

Model card: `new_keynesian` v1.0.1 (sha256 `bdaebdd44087...`).
Deterministic run at the time: `ba353b6662411f29`, R1, terminal `REJECTED`.

Both sandboxed critics (`critic_fidelity`, `critic_adequacy`) completed with
exit 0 and produced substantive text, but hit the 8-step budget before writing
`result.json`. The full assistant text is preserved in the two `.md` files.
The step budget was raised to 12 after this run.

The critics independently agreed with the mechanical REJECTED and caught two
advisory-packet defects that were fixed immediately:

1. `metrics_gate.json` marked IPCA h=6 as pass despite `focus_ratio=1.114` and
   DM-vs-Focus p=0.029. The gate file now applies the full core rule.
2. The gate file included satellite GDP rows. It now excludes `satellite=True`.

Their remaining findings (gate-label naming, tautological D2 check, AR(p) vs
AR(1) wording, bridge sample, two-origin stability, untested Taylor principle)
are recorded in `docs/STATUS.md` as v1.1 follow-ups.

Final deterministic rerun after the advisory-gate and gap-threshold fixes:
`e2a56cb8cc6d925e` (same forecasts, terminal `REJECTED`, 3 high/3 medium).
