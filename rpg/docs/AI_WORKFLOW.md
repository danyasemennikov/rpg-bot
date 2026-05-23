# AI Workflow

This project uses multiple AI-assisted working modes.

The goal is to avoid mixing design decisions, implementation planning, Codex execution, and technical review in one conversation.

---

## Working chats

### RPG — Design Room

Purpose:

- game design decisions
- route identity
- class fantasy
- PvE/PvP philosophy
- economy and reward direction
- player experience

Output:

- Decision Packet

Does not output Codex prompts by default.

---

### RPG — Balance Lab

Purpose:

- route/class balance
- PvE pressure
- PvP pressure
- build matchups
- numeric risk analysis
- progression speed
- reward feel

Output:

- balance Decision Packet
- risks
- done criteria

Does not output Codex prompts by default.

---

### RPG — Producer / Specs

Purpose:

- convert Decision Packets into implementation plans
- define PR scope
- define files
- define tests
- define non-goals
- prepare Codex-ready prompts

Output:

- implementation plan
- Codex prompt

---

### RPG — Codex Review / Integration

Purpose:

- review Codex summaries and diffs
- find blockers
- find cheap tails
- prepare fix prompts
- decide whether a PR can merge
- provide test commands

Output:

- blocker list
- fix prompt if needed
- merge/test guidance if ready

---

## Handoff protocol

When a chat finishes its role for the current stage, it must stop and produce a handoff packet instead of continuing into another role.

Format:

```text
HANDOFF PACKET

From:
To:
Topic:
Current confirmed state:
Decision / Result:
Why:
Scope:
Non-goals:
Risks:
Done criteria:
Open questions:
Recommended next action:
```

Routing:

- Design Room / Balance Lab → Producer / Specs
- Producer / Specs → Codex
- Codex result → Codex Review / Integration
- Codex Review / Integration after merge → update Project State and choose next stage

---

## Project state rule

`rpg/docs/PROJECT_STATE_CURRENT.md` is the source of truth for confirmed merged state.

Any PR that changes confirmed project state must update this file in the same PR.

If the PR does not change confirmed state, the PR summary must explicitly say:

```text
PROJECT_STATE_CURRENT.md not updated: no confirmed project state change.
```

---

## Source of truth order

Use this priority order:

1. Explicit user confirmation that a PR was merged and tests are green.
2. Current GitHub `main`.
3. Repository docs.
4. Chat discussion / planned work.

Planned work is not confirmed state until merged.

---

## Persistent constraints

Unless explicitly changed by a new accepted Decision Packet:

- Teleport is skipped.
- Targeting rollout is frozen.
- Do not mix unrelated large scopes in one PR.
- Cheap tails should be fixed before merge.
- Do not replace existing rails with a new foundation unless necessary.
