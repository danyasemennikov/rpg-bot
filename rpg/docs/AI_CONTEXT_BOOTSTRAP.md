# AI Context Bootstrap

- Status: Active
- Authority: Supporting context-loading protocol
- Last reconciled: 2026-09-23, against `ad5435e577e45e63da2ca57af2296203d88cedd5`

Use this checklist to enter a task without relying on chat memory.

## Establish the actual state

1. Identify the repository, task mode, working branch, base branch, and actual HEAD.
2. Verify whether the checkout is clean before editing. Preserve unrelated changes.
3. Read [../AGENTS.md](../AGENTS.md), [DOCS_INDEX.md](DOCS_INDEX.md), and
   [PROJECT_STATE_CURRENT.md](PROJECT_STATE_CURRENT.md).
4. Distinguish confirmed `main` from candidate-branch changes. A plan, report, Draft
   PR, or test result does not prove that code is merged or deployed.

## Load only relevant context

- Use [systems/README.md](systems/README.md) to find current implementation owners.
- Load the applicable foundation for durable design intent.
- Load an Epic report to understand a delivery boundary, migration, or historical
  validation—not as a replacement for current code.
- Load evidence only with its recorded commit, inputs, and limitations.
- Use [ROADMAP_CURRENT.md](ROADMAP_CURRENT.md) for forward priority, and
  [DECISIONS_LOG.md](DECISIONS_LOG.md) for accepted decisions.

Do not infer implementation from plans. Preserve the classless build philosophy and
established transaction, persistence, settlement, and migration authorities unless an
accepted task explicitly changes them. Record unknowns instead of inventing state or
resolving open design questions.

## Execute the task contract

- Follow the task's explicit scope, non-goals, and validation restrictions.
- Read the target files and directly related neighbors before editing.
- Do not assume every task requires pytest; use the validation policy authorized for
  that task. Conversely, do not skip required checks unless the task forbids them.
- Keep merge state, deployment state, review approval, and validation evidence as
  separate facts.

## Handoff

Report the verified base/head, scope completed, files changed, validation performed,
evidence provenance, unresolved questions, risks, and the next responsible role. Use
the lifecycle and statuses in [AI_WORKFLOW.md](AI_WORKFLOW.md).
