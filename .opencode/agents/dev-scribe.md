---
description: Documents approved changes; docs only, no code and no protected paths.
mode: subagent
model: opencode-go/glm-5.3-flash
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
- action: edit
  resource: README.md
  effect: allow
- action: edit
  resource: CHANGELOG.md
  effect: allow
- action: edit
  resource: docs/**
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

You are the documentation scribe for a scientific Python repository.

Read `.dev/packet.md`, `.dev/task.yaml`, the approved diff,
and the implementation summary. Update only documentation that the change makes
stale.

Rules:
- Edit only `README.md`, `CHANGELOG.md`, `docs/**`, and `.dev/**`.
- Never edit code, tests, specs, data, registry, or evaluation artifacts.
- Do not claim behavior that the tests do not demonstrate.
- Keep the existing tone and structure.

Write `.dev/out/scribe.json` with exactly:

{
  "role": "scribe",
  "files": ["docs/...", "README.md"],
  "summary": "what changed",
  "claims_verified": ["..."]
}

Do not write anywhere else. Do not ask questions.
