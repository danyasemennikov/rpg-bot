# Google AI Workflow

This document provides a concise practical overview of the new Google-based workflow for the RPG bot project. The goal of this workflow is to keep the boundary between theoretical design and implementation review clean, while preventing context fragmentation.

## Overview of the Workflow

The workflow relies on Gemini/Gems for planning, design, and PR review, and Jules for code implementation.

### Gemini/Gems

We use two specific Gemini Gems to handle distinct phases of the development lifecycle:

1. **RPG — Design & Balance (Gemini Gem)**
   - Responsible for theory, game design, balance, route identity, class/archetype fantasy, PvE/PvP philosophy, economy/rewards, and player experience.
   - Makes design decisions *before* any implementation begins.
   - Does **not** write production code or create PRs.

2. **RPG — Producer / Jules Review (Gemini Gem)**
   - Responsible for translating design decisions into concrete implementation plans.
   - Defines coherent PR scopes, writes detailed prompts for Jules, reviews Jules' PRs, identifies blockers and cheap tails, and provides merge/test guidance.

### Jules

- **Jules** is the current default coding agent for implementation PRs.
- Jules receives clear, scoped prompts from the "Producer / Jules Review" Gem.
- Jules implements the requested features, runs tests, and submits PRs for review.

## GitHub main as the Source of Truth

- While Gemini Gems and Jules assist in designing and implementing features, **GitHub `main`** remains the ultimate source of truth for the project.
- Documentation, including `PROJECT_STATE_CURRENT.md`, must be updated to reflect the merged state of the repository.
- Unmerged ideas, plans, and discussions do not constitute confirmed project state.
