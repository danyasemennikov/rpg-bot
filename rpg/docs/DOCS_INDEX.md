# Documentation Index

- Status: Active
- Authority: Canonical navigation entry
- Last reconciled: 2026-09-23, against `ad5435e577e45e63da2ca57af2296203d88cedd5`

Start here.

- Current merged state: [PROJECT_STATE_CURRENT.md](PROJECT_STATE_CURRENT.md)
- Forward roadmap: [ROADMAP_CURRENT.md](ROADMAP_CURRENT.md)
- Contributor and agent rules: [../AGENTS.md](../AGENTS.md)
- Workflow: [AI_WORKFLOW.md](AI_WORKFLOW.md)
- System implementation map: [systems/README.md](systems/README.md)

These documents have separate authority. The current-state summary does not own
future work; the roadmap does not prove implementation; foundations describe durable
intent; Epic reports and evidence record delivery at stated commits.

## Authority map

| Question | Authority |
|---|---|
| What is merged on the reconciled baseline? | [PROJECT_STATE_CURRENT.md](PROJECT_STATE_CURRENT.md) |
| What should be considered next? | [ROADMAP_CURRENT.md](ROADMAP_CURRENT.md) |
| What rules constrain contributors and agents? | [../AGENTS.md](../AGENTS.md) |
| How does work move from design to merge? | [AI_WORKFLOW.md](AI_WORKFLOW.md) |
| Where is a system implemented and documented? | [systems/README.md](systems/README.md) |
| Which decisions are accepted? | [DECISIONS_LOG.md](DECISIONS_LOG.md) |
| Which ideas are uncommitted? | [BACKLOG.md](BACKLOG.md) |
| Where is the compact legacy-friendly technical adapter? | [CLAUDE.md](CLAUDE.md) |
| What was delivered by a merged Epic? | [epics/README.md](epics/README.md) |
| What was measured, and at which commit? | [evidence/README.md](evidence/README.md) |
| What was true historically? | [archive/README.md](archive/README.md) |

## Foundations

Foundations express durable design intent. They are not proof that every described
mechanic is implemented.

- [Game foundation](foundation/GAME_FOUNDATION.md)
- [Loot, crafting, and progression foundation](foundation/LOOT_CRAFT_PROGRESSION_FOUNDATION.md)
- [PvP ruleset foundation](foundation/PVP_RULESET_FOUNDATION.md)
- [World skeleton](foundation/WORLD_SKELETON_V1.md)
- [Balance foundation](BALANCE_FOUNDATION_ALPHA_TO_RELEASE.md) — retained at its
  compatibility path because tests consume it.

## Systems

[systems/README.md](systems/README.md) maps combat, world/travel, gear,
professions/economy, PvE, and PvP documentation to current implementation owners.
It also catalogues compatibility-retained system and pass documents.

## Merged Epic delivery records

[epics/README.md](epics/README.md) catalogues the PR229, PR230, and PR231 delivery
reports and the historical open-world pass records. These reports preserve the
validation and limitations that applied to their delivery baseline.

## Evidence

[evidence/README.md](evidence/README.md) records provenance and interpretation limits
for checked artifacts. Generated balance reports stay at their original paths and
remain byte-for-byte unchanged.

## Historical and superseded material

[archive/README.md](archive/README.md) catalogues status snapshots, obsolete workflow
material, rollout contracts, superseded specifications, and the old status template.
Archived claims remain historically accurate for their period and do not compete with
current authorities.

## Compatibility-retained files

The following documents remain at the repository-root docs paths because Python tests
consume their path or text. Their physical location does not make them current
authorities.

- [PROJECT_STATE_CURRENT.md](PROJECT_STATE_CURRENT.md) — canonical current summary,
  with a clearly marked historical compatibility excerpt.
- [CHARACTER_BUILDS_COMBAT_IDENTITY_V1.md](CHARACTER_BUILDS_COMBAT_IDENTITY_V1.md) —
  merged PR231 delivery record.
- [TARGET_PATTERN_SYSTEM_V1.md](TARGET_PATTERN_SYSTEM_V1.md) — legacy targeting chapter.
- [BALANCE_FOUNDATION_ALPHA_TO_RELEASE.md](BALANCE_FOUNDATION_ALPHA_TO_RELEASE.md) —
  scoped foundation plus historical balance notes.
- The historical open-world pass records catalogued in [epics/README.md](epics/README.md).
- [ALPHA_ROUTE_CLASS_BALANCE_REPORT_V1.md](ALPHA_ROUTE_CLASS_BALANCE_REPORT_V1.md)
  and [ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md](ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md)
  — unchanged generated diagnostics.

## Reading paths

1. **New AI context:** `AGENTS` → this index → current state →
   [AI_CONTEXT_BOOTSTRAP.md](AI_CONTEXT_BOOTSTRAP.md) → workflow → relevant system map.
2. **Architecture/design:** common entry path → roadmap → relevant foundation → current
   implementation map → applicable Epic report/evidence → decisions log.
3. **Implementation:** common entry path → frozen task contract → relevant system/spec →
   target and neighboring code → scoped acceptance criteria.
4. **PR review:** verified base/head → frozen contract → actual diff → current state and
   system map → report/evidence provenance → focused acceptance checklist.
5. **Gameplay/content design:** game foundation → relevant world/loot/PvP foundation →
   implemented capability boundaries → evidence → roadmap/backlog.
6. **Historical investigation:** archive index → historical document at its baseline →
   associated PR/commit → successor delivery report → current state.

Load only the documents relevant to the task. A new chat should not consume every
foundation, report, and archive by default.
