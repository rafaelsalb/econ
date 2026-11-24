# Development canaries

These are held-out tasks with known-good outcomes. Run them after changing a
prompt, model, gate, or scheduler. They never enter the normal ready queue.

`econ dev canary --validate` checks the contracts. `econ dev canary --run --fake`
builds a disposable repository per canary and runs the real orchestrator against
it with the deterministic fake runner. Results are written to
`reports/dev_canaries.md`, `runs/dev/canaries/latest.json`, and the dashboard.

## Growing the suite from failures

A failed run, or an escalation after the round budget is exhausted, writes a
*proposed* canary contract to `proposed/CANARY-NNNN.yaml`, copied from the
failed task's own goal, acceptance, scope, and demo, with the original failure
and expected outcome recorded in `notes`. Nothing in `proposed/` runs.

Promotion is a separate human step, and deliberately so — the suite only stays
honest if a person curates it:

1. Read `proposed/CANARY-NNNN.yaml` and its `notes`.
2. Fix the demo fixture so the contract is deterministic, and state the
   expected outcome in `notes`.
3. Run `econ dev canary --promote CANARY-NNNN`.

Promotion validates the contract and refuses canaries without a demo fixture —
the suite runs the fake runner, so an indeterministic canary is worthless. The
nightly maintenance report lists anything waiting in `proposed/`.
