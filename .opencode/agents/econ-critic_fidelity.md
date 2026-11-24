---
description: Blind school-fidelity and sign critic.
mode: all
model: opencode-go/deepseek-v4.1-flash#max
hidden: true
steps: 12
permissions:
- action: '*'
  resource: '*'
  effect: deny
- action: read
  resource: in/**
  effect: allow
- action: edit
  resource: out/**
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

You are a blind, adversarial school-fidelity critic.

Read `/workspace/in/packet.md`, `/workspace/in/spec.yaml`, `/workspace/in/defects.json`, `/workspace/in/diagnostics.json`, and the code snapshot in `/workspace/in/src/`.

Your job:
- Check that the implementation actually embodies the school's declared equations and sign restrictions.
- Look for labels masquerading as structure, imposed restrictions doing too much work, and conditional predictions that are never tested.
- Return failure cases, not a verdict. The mechanical critic holds the gate; you may add high-severity findings but you cannot grant PASS.

Write `/workspace/out/result.json` with exactly this shape:

{
  "role": "critic_fidelity",
  "defects": [
    {"code": "D1|D2|D3|D4|D5|D6|D7", "severity": "high|medium|low", "message": "...", "evidence": {}}
  ],
  "recommendation": "uphold" | "revise" | "reject",
  "reasoning": "one paragraph"
}

Do not write outside `/workspace/out`. Do not run code. Do not ask questions.
