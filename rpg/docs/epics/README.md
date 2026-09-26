# Epic Delivery Reports

- Status: Active catalogue
- Authority: Navigation for merged delivery history
- Last reconciled: 2026-09-26, against `27347ece2b17108a1aed1f6eb01f2a395480e6c9`

Epic reports record what a candidate delivered, how it was migrated and validated,
and which limitations applied at that baseline. They do not replace current code,
[PROJECT_STATE_CURRENT.md](../PROJECT_STATE_CURRENT.md), or system documentation.

## Active Draft candidates

| Delivery record | Contract | Disposition |
|---|---|---|
| [Professions & Economy V1](PROFESSIONS_ECONOMY_V1_REPORT.md) | PEV1-1 Stage 3 | Draft PR candidate; not merged or deployed |

## Merged Epics

| Delivery record | Repository PR | Disposition | Later scope notes |
|---|---:|---|---|
| [Playable Alpha Vertical Slice V1](PLAYABLE_ALPHA_VERTICAL_SLICE_V1.md) | [#229](https://github.com/danyasemennikov/rpg-bot/pull/229) | Merged | PR230 replaced the older partial victory-reward boundary with versioned settlement for eligible V1 encounters and expanded field gear acquisition. |
| [Field Loot & Gear Progression V1](FIELD_LOOT_AND_GEAR_PROGRESSION_V1.md) | [#230](https://github.com/danyasemennikov/rpg-bot/pull/230) | Merged | PR231 preserved its item/settlement guarantees while changing combat/build authorities and normalizing mastery through canonical families. |
| [Character Builds & Combat Identity V1](../CHARACTER_BUILDS_COMBAT_IDENTITY_V1.md) | [#231](https://github.com/danyasemennikov/rpg-bot/pull/231) | Merged | Current report remains at a compatibility-retained path because tests consume it. |

Merge does not establish deployment. Validation recorded inside each report applies to
the stated candidate and evidence baseline.

## Historical open-world delivery records

The pass documents listed in [systems/README.md](../systems/README.md) remain at their
test-consumed paths. They preserve the exact scope and validation of PR3A–PR3P-era
delivery. Later PR229–PR231 capabilities supersede some limitations, but the historical
bodies remain period-accurate.

The two larger rollout contracts were moved to
[archive/rollouts](../archive/README.md#rollout-contracts).
