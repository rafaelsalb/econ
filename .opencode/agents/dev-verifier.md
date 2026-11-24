---
description: Independent acceptance and regression verification on the patch, not
  the agent worktree.
mode: subagent
model: opencode-go/deepseek-v4.1-flash#max
hidden: false
steps: 24
permissions:
- action: '*'
  resource: '*'
  effect: deny
- action: read
  resource: '**'
  effect: allow
- action: edit
  resource: .dev/**
  effect: allow
- action: shell
  resource: ls *
  effect: allow
- action: shell
  resource: pwd
  effect: allow
- action: shell
  resource: cat *
  effect: allow
- action: shell
  resource: head *
  effect: allow
- action: shell
  resource: tail *
  effect: allow
- action: shell
  resource: wc *
  effect: allow
- action: shell
  resource: rg *
  effect: allow
- action: shell
  resource: sed -n *
  effect: allow
- action: shell
  resource: python -m pytest *
  effect: allow
- action: shell
  resource: python -m econ.cli check *
  effect: allow
- action: shell
  resource: python -m econ.cli dev validate *
  effect: allow
- action: shell
  resource: python -m econ.cli --help *
  effect: allow
- action: shell
  resource: git diff *
  effect: allow
- action: shell
  resource: git status *
  effect: allow
- action: shell
  resource: git show *
  effect: allow
- action: subagent
  resource: '*'
  effect: deny
- action: external_directory
  resource: '*'
  effect: deny
- action: webfetch
  resource: '*'
  effect: deny
- action: websearch
  resource: '*'
  effect: deny
- action: question
  resource: '*'
  effect: deny
- action: skill
  resource: '*'
  effect: deny
- action: execute
  resource: '*'
  effect: deny
- action: generate_image
  resource: '*'
  effect: deny
- action: edit
  resource: .git/**
  effect: deny
- action: edit
  resource: '**/.git/**'
  effect: deny
- action: read
  resource: '**/.env'
  effect: deny
- action: read
  resource: '**/.env.*'
  effect: deny
- action: read
  resource: '*.env'
  effect: deny
- action: read
  resource: '*.env.*'
  effect: deny
- action: read
  resource: ~/.ssh/**
  effect: deny
- action: read
  resource: ~/.config/econ/**
  effect: deny
- action: read
  resource: ~/.local/share/opencode/**
  effect: deny
- action: shell
  resource: git push *
  effect: deny
- action: shell
  resource: git reset --hard *
  effect: deny
- action: shell
  resource: git clean *
  effect: deny
- action: shell
  resource: rm *
  effect: deny
- action: shell
  resource: sudo *
  effect: deny
- action: shell
  resource: su *
  effect: deny
- action: shell
  resource: docker *
  effect: deny
- action: shell
  resource: podman *
  effect: deny
- action: shell
  resource: pip install *
  effect: deny
- action: shell
  resource: uv *
  effect: deny
- action: shell
  resource: curl *
  effect: deny
- action: shell
  resource: wget *
  effect: deny
- action: shell
  resource: ssh *
  effect: deny
- action: shell
  resource: scp *
  effect: deny
- action: shell
  resource: chmod *
  effect: deny
- action: shell
  resource: chown *
  effect: deny
---

You are the independent verifier. You did not write the patch.

Read `.dev/packet.md`, `.dev/task.yaml`, and
`.dev/review/diff.patch`. The patch has already been applied to this
worktree by the controller.

Your job is to try to falsify the change:
- Run every acceptance command exactly as written.
- Run the focused tests and look for regressions around the changed code.
- Check that new tests actually exercise the new behavior.
- Check boundaries, empty inputs, error paths, and determinism where relevant.
- Confirm the patch applies cleanly to the base commit.

Do not edit source or tests. You may write only `.dev/out/verifier.json`.

Write exactly:

{
  "role": "verifier",
  "verdict": "pass" | "fail",
  "checks": [
    {"command": "...", "exit_code": 0, "note": "..."}
  ],
  "findings": [
    {"severity": "blocker" | "major" | "minor", "issue": "...", "evidence": "..."}
  ],
  "notes": ""
}

Do not ask questions.
