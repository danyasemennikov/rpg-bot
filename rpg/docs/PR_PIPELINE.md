# PR Pipeline

This document describes the typical lifecycle of a feature or fix in the RPG bot project, moving from initial idea to merged code.

### Pipeline Statuses

- **Idea:** A rough concept or discussion in the Design & Balance Gem.
- **Decision Ready:** A structured Decision Packet has been created by the Design & Balance Gem.
- **Spec Ready:** The Producer Gem has converted the Decision Packet into an implementation plan and Jules prompt.
- **Sent to Jules:** The prompt has been handed off to Jules.
- **Jules PR Open:** Jules has submitted the PR for review.
- **Review Needed:** The Producer Gem is currently reviewing the PR.
- **Fix Needed:** Blockers or cheap tails were found; Jules needs to make adjustments.
- **Ready to Merge:** The PR is approved and tests are passing.
- **Merged + Tests Green:** The code is in `main`, tests pass, and `PROJECT_STATE_CURRENT.md` is updated (if applicable).

### Status Tracker Template

| Feature / Task | Status | Owner | Notes |
| :--- | :--- | :--- | :--- |
| [Feature Name] | [Status] | [Gem/Jules] | [Brief update or blocker] |
| e.g., Weapon mastery scaling | Decision Ready | Design Gem | Awaiting Producer review |
| e.g., Unify enemy turn logic | Jules PR Open | Jules | Tests passing, need Producer review |
