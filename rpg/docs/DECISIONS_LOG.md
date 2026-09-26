# Decisions Log

- Status: Active
- Authority: Canonical for accepted decisions; not current state or roadmap
- Last reconciled: 2026-09-26, against `27347ece2b17108a1aed1f6eb01f2a395480e6c9`

This log is used to track **accepted decisions only**. Loose ideas or theoretical discussions should not be recorded here.

Operational status belongs in `PROJECT_STATE_CURRENT.md`; forward candidates belong in
`ROADMAP_CURRENT.md`. A decision may be implemented, pending, or superseded without
becoming a competing status summary.

## Template for Accepted Decisions

### Decision: [Short Title]
- **Date:** [YYYY-MM-DD]
- **Context:** [Briefly explain the problem or discussion that led to this decision.]
- **Decision:** [Clearly state the finalized decision.]
- **Impact:** [What parts of the project, codebase, or balance this affects.]
- **Status:** [e.g., Pending Implementation, Implemented in PR #123]

---

### Decision: Freeze Professions & Economy V1
- **Date:** 2026-09-24
- **Context:** The post-PR232 baseline had persisted gathering and a four-recipe
  chapter subset but no accepted full V1 economy boundary.
- **Decision:** Implement PEV1-1 Stage 3 exactly: 12 professions, 63 active recipes,
  28 mandatory materials, permanent knowledge, lossless migration, durable economic
  receipts, and ru/en/es UX. All eight new recovery outputs use `item_type='potion'`;
  heal/mana authority is `stat_bonus_json`, and environmental sources have one runtime
  authority.
- **Impact:** Professions, sources, crafting outputs, economy mutations, journal UX,
  migrations, acceptance journeys, evidence, and documentation.
- **Status:** Accepted contract; implementation is an unmerged Draft-PR candidate.

---

### Decision: Astra / Sol Acceptance Workflow
- **Date:** 2026-09-23
- **Context:** Architecture, implementation, acceptance, and landing responsibilities
  need explicit separation even when the same application hosts multiple roles.
- **Decision:** Use the lifecycle in `AI_WORKFLOW.md`: Astra audit and frozen contract,
  Sol Draft-PR implementation, Astra acceptance and narrow re-review, then user merge
  after approval and post-merge state reconciliation.
- **Impact:** Supersedes active use of the old Google AI, Gemini, Jules, and parallel
  PR-pipeline documents. Those files remain in `archive/workflow/` as history.
- **Status:** Accepted; implemented by Documentation Architecture & Consolidation V1.

---

### Decision: Migrate to Google AI Workflow (Archived / Superseded)
- **Date:** 2026-06-02
- **Context:** The previous ChatGPT/Codex workflow caused context fragmentation because agents did not reliably share memory.
- **Decision:** Move to a two-Gem + Jules workflow. Gemini handles design, spec, and review, while Jules handles code implementation.
- **Impact:** Documentation updated (AGENTS.md, AI_WORKFLOW.md, etc.) to reflect the new roles.
- **Status:** Implemented in PR #213; superseded first by Codex Workflow Restoration
  and then by the Astra / Sol acceptance workflow above.
