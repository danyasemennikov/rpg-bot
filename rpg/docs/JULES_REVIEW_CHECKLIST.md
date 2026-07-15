# Jules Review Checklist (Archived / Inactive)

Archived workflow experiment checklist. Do not use this as the current implementation source of truth; current implementation review should happen through Codex Review / Integration.

### Review Checklist

- [ ] **Scope Adherence:** Does the PR solve the stated goal? Is there any scope creep?
- [ ] **Blockers & Cheap Tails:** Are there any immediate blockers? Are there any small, easy-to-fix issues ("cheap tails") that should be addressed before merging?
- [ ] **Tests:** Have tests been written (if required)? Do the standard tests pass?
- [ ] **Project State:** Has `PROJECT_STATE_CURRENT.md` been correctly updated if the PR changed confirmed state? (Or, if it didn't, does the PR summary explicitly state that no state changed?)
- [ ] **i18n Compatibility:** Are all new player-facing text strings properly routed through the i18n system?
- [ ] **Legacy Compatibility:** Are legacy aliases or paths preserved where necessary?
- [ ] **Battle State:** If combat logic was touched, does it safely interact with `context.user_data['battle']`? Was it incrementally refactored rather than rewritten?
- [ ] **Cooldowns & Rewards:** Are cooldown resets and post-battle reward logic maintained correctly?
- [ ] **Routes & Alpha Gate:** If adding or modifying routes, do they adhere to alpha readiness policies?
- [ ] **Database Safety:** Are schema changes backward-compatible and explicitly justified?
