# Google AI Workflow

This document is an archived overview of the inactive Google-based workflow experiment for the RPG bot project. The goal of this workflow is to keep the boundary between theoretical design and implementation review clean, while preventing context fragmentation.

## Overview of the Workflow

This archived workflow relied on Gemini/Gems for planning, design, and PR review, and Jules for code implementation. It is not the current source of truth for implementation.

### Gemini/Gems

The inactive experiment used two specific Gemini Gems to handle distinct phases of the development lifecycle:

1. **RPG — Design & Balance (Gemini Gem)**
   - Responsible for theory, game design, balance, route identity, class/archetype fantasy, PvE/PvP philosophy, economy/rewards, and player experience.
   - Makes design decisions *before* any implementation begins.
   - Does **not** write production code or create PRs.

2. **RPG — Producer / Jules Review (Gemini Gem) — archived/inactive**
   - Responsible for translating design decisions into concrete implementation plans.
   - Defined coherent PR scopes, wrote detailed prompts for Jules, reviewed Jules PRs, identified blockers and cheap tails, and provided merge/test guidance.

### Jules (archived/inactive)

- **Jules is not the current implementation workflow. Codex is the current implementation coding agent.**
- Historically, Jules received clear, scoped prompts from the "Producer / Jules Review" Gem.
- Historically, Jules implemented requested features, ran tests, and submitted PRs for review.

## GitHub main as the Source of Truth

- While archived Gemini Gems and Jules docs may describe prior experiments, **GitHub `main`** remains the ultimate source of truth for the project.
- Documentation, including `PROJECT_STATE_CURRENT.md`, must be updated to reflect the merged state of the repository.
- Unmerged ideas, plans, and discussions do not constitute confirmed project state.
