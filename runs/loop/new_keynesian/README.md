# Critic loop artifacts

This directory is the file-based interface of the Phase 1 loop. Each round has:

| File | Consumer | Contents |
|---|---|---|
| `theorist_packet.md` | Theorist | Frozen card hash, round decision, admissible revision |
| `modeler_packet.md` | Modeler | Typed defects only; no validation score table |
| `critic_packet.md` | Critics | Card hash, code, diagnostics, typed defects |
| `defects.json` | Driver / human | Machine-readable defect ledger |
| `diagnostics.json` | Critics / human | Coefficients, t-stats, Ljung-Box, condition numbers, stability, IRF signs, sanity |
| `metrics.csv` | Human / evaluator | Out-of-sample metrics (not passed to the modeler) |
| `decision.json` | Driver | Status, blocking defects, next revision |
| `revision.json` | Modeler | The rung of the pre-registered ladder applied next |

The driver (`src/econ/loop.py`) is deterministic. It applies the revision ladder
and computes the gate. The packets are deliberately shaped so an LLM agent can
occupy each role:

1. The **theorist** reads the frozen card and the defect ledger, and may only
   choose an admissible rung. The card is not editable inside the loop.
2. The **modeler** receives `modeler_packet.md` (defects, no scores) and applies
   exactly one pre-registered change.
3. The **critics** read `critic_packet.md` blind and return typed defects. The
   mechanical critic is authoritative for the gate; the LLM critic is advisory.
4. The **driver** recomputes the scoreboard and the gate. No agent can pass a
   model on its own.

## Current terminal state

`PASS_WITH_LIMITATIONS` after R1 → R2 → R3. See
`../../specs/new_keynesian.decision.json` and `round-3/defects.json`.

An independent LLM critic review is stored in `external_review.md`. It is
advisory and does not change the mechanical gate.
