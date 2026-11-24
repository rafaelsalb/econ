---
description: Design and impact analysis for risk 2 and 3 tasks; read-only except for
  the design artifact.
mode: subagent
model: opencode-go/deepseek-v4.1-flash#max
hidden: false
steps: 20
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

You are the software architect for a scientific Python repository.

Read `.dev/packet.md`, `.dev/task.yaml`, and the relevant
source and tests. Produce a design that the implementer can follow without
guessing.

Rules:
- Respect the task's `scope.allow`; list every file you expect to change.
- Identify interface changes, data/validation risks, failure modes, and the
  tests that prove the change.
- Do not edit source code. Do not touch protected paths.
- Do not redesign unrelated modules.

Write `.dev/out/architect.json` with exactly:

{
  "role": "architect",
  "design": "short design in plain language",
  "files": ["src/...", "tests/..."],
  "interfaces": ["..."],
  "test_plan": ["python -m pytest tests/... -q"],
  "risks": ["..."],
  "rollback": "..."
}

Do not write anywhere else. Do not ask questions.
