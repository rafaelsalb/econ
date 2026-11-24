---
description: Run the held-out canary suite
agent: dev-lead
subagent: false
---

Run `python -m econ.cli dev canary --validate` and then
`python -m econ.cli dev canary --run --fake`. Summarize pass/fail, rounds, and
any regression in the pipeline. Do not change the canary contracts to make them
pass.
