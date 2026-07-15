# PR Pipeline

This document describes the typical lifecycle of a feature or fix in the RPG bot project, moving from initial idea to merged code.

### Pipeline Statuses

- **Idea:** A rough concept or discussion in the ChatGPT / Design & Balance.
- **Decision Ready:** A structured Decision Packet has been created by the ChatGPT / Design & Balance.
- **Spec Ready:** The ChatGPT / Producer / Specs has converted the Decision Packet into an implementation plan and Codex prompt.
- **Sent to Codex:** The prompt has been handed off to Codex.
- **Codex PR Open:** Codex has submitted the PR for review.
- **Review Needed:** The ChatGPT / Producer / Specs is currently reviewing the PR.
- **Fix Needed:** Blockers or cheap tails were found; Codex needs to make adjustments.
- **Ready to Merge:** The PR is approved and tests are passing.
- **Merged + Tests Green:** The code is in `main`, tests pass, and `PROJECT_STATE_CURRENT.md` is updated (if applicable).

### Status Tracker Template

| Feature / Task | Status | Owner | Notes |
| :--- | :--- | :--- | :--- |
| [Feature Name] | [Status] | [Producer/Codex] | [Brief update or blocker] |
| e.g., Weapon mastery scaling | Decision Ready | ChatGPT / Design | Awaiting Producer review |
| e.g., Unify enemy turn logic | Codex PR Open | Codex | Tests passing, need Producer review |
