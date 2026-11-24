# Development canaries

These are held-out tasks with known-good outcomes. Run them after changing a
prompt, model, gate, or scheduler. They never enter the normal ready queue.

`econ dev canary --validate` checks the contracts. `econ dev canary --run --fake`
builds a disposable repository per canary and runs the real orchestrator against
it with the deterministic fake runner.
