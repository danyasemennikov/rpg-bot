# AI Workflow

This project uses a Google AI workflow with Gemini/Gems and Jules.

The goal is to avoid context fragmentation and avoid mixing theoretical design with concrete implementation and review.

---

## Working modes

### 1. RPG — Design & Balance (Gemini Gem)

Purpose:

- game design
- balance
- route identity
- class/archetype fantasy
- PvE/PvP philosophy
- economy/rewards
- player experience
- theoretical decisions before implementation

Output:

- Decision Packet
- balance specifications
- risks

Does not output implementation code or PRs.

---

### 2. RPG — Producer / Jules Review (Gemini Gem)

Purpose:

- implementation plans
- coherent PR scope
- Jules prompts
- PR review
- blockers / cheap tails
- fix prompts
- merge/test guidance

Output:

- implementation plan
- Jules prompt
- blocker list / fix prompt if needed
- merge/test guidance if ready

---

### 3. Implementation (Jules)

Purpose:

- write code based on Jules prompts
- run tests
- implement PRs

Jules is the current default coding agent for implementation PRs.

---

## Handoff protocol

When a Gem finishes its role for the current stage, it must stop and produce a handoff packet instead of continuing into another role.

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

- Design & Balance → Producer / Jules Review
- Producer / Jules Review → Jules
- Jules result → Producer / Jules Review
- Producer / Jules Review after merge → update Project State and choose next stage

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
