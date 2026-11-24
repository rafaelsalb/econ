---
description: Reproduce a bug as a failing test before implementation
agent: dev-reproducer
subagent: false
---

Read the bug report in $ARGUMENTS and the current repository. Write the smallest
test under `tests/` that fails for the reported reason on the base commit. Do not
fix the bug or edit source.
