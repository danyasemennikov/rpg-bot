# Decisions Log

This log is used to track **accepted decisions only**. Loose ideas or theoretical discussions should not be recorded here.

Current workflow note: Codex Workflow Restoration supersedes the prior Google AI / Jules implementation workflow experiment; Codex is the active implementation coding agent.

## Template for Accepted Decisions

### Decision: [Short Title]
- **Date:** [YYYY-MM-DD]
- **Context:** [Briefly explain the problem or discussion that led to this decision.]
- **Decision:** [Clearly state the finalized decision.]
- **Impact:** [What parts of the project, codebase, or balance this affects.]
- **Status:** [e.g., Pending Implementation, Implemented in PR #123]

---

### Decision: Migrate to Google AI Workflow (Archived / Superseded)
- **Date:** 2026-06-02
- **Context:** The previous ChatGPT/Codex workflow caused context fragmentation because agents did not reliably share memory.
- **Decision:** Move to a two-Gem + Jules workflow. Gemini handles design, spec, and review, while Jules handles code implementation.
- **Impact:** Documentation updated (AGENTS.md, AI_WORKFLOW.md, etc.) to reflect the new roles.
- **Status:** Implemented in PR #213; superseded by Codex Workflow Restoration.
