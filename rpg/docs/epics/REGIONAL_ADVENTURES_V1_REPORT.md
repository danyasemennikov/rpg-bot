# Regional Adventures & Opportunities V1

- Status: Draft PR candidate; unmerged and not deployed
- Contract: RAV1-1
- Frozen base: `ebd8f73ade53fcadb89942b703a947782276ea1c` (merged PR #233)
- Candidate branch: `codex/regional-adventures-opportunities-v1`
- Tested code commit: `4f38f20`
- Final Draft-PR head: the commit containing the final evidence refresh; its exact
  SHA is recorded in the Draft PR body and final handoff because a commit cannot
  embed its own object ID.
- Human validation: not yet run

## Delivered candidate

RAV1 adds a post-Chapter-I nonlinear Journal without creating Chapter II, a global
campaign, a region order, a finale, or a completion percentage. Five peer regional
summaries lead to seven independent local projects, twelve inspectable facts, two
finite delivery requests, one independent cache, three repeatable local jobs, two
named targets, and two new mixed encounter recipes. Existing hunts, combat,
professions, equipment, travel, inventory, and character progression remain separate
authorities and remain available after finite records are resolved.

The exact frozen counts are enforced at startup and in tests: 34 top-level catalogue
records; seven projects; 18 steps; 22 objectives using exactly seven kinds; five short
finite opportunities; ten discoveries plus two auxiliary inspections; ten one-time
claims; three standing deliveries; six activated/repaired hunts and zero new hunt
definitions; two named targets; two new and two retained mixed encounters; seven
service additions; three permanent two-outcome choices plus the non-branching Sled
method; and ru/en/es copy with identical key and placeholder structure.

## Authority and implementation map

- `game/regional_catalog.py` is data-only and freezes the complete catalogue and
  reference validation. `game/regional_opportunities.py` is a read-only aggregator.
- `game/regional_schema.py` owns the exact five-table schema and marker. It accepts
  only the missing schema or exact target, fails closed on incompatible structures,
  rolls back injected migration failure, and is restart-idempotent.
- `game/regional_adventures.py` owns project, fact, claim, delivery, pin, token, and
  replay transactions. One-time claims use stable content identity; standing work
  consumes one fresh basket per receipt and never creates a finite claim.
- `game/regional_objectives.py` observes successful personal craft commits and
  captures immutable project bindings when the existing open-world roster locks.
  Combat progress is applied once inside authoritative settlement T2 and only to
  eligible recipients in the settlement plan.
- `game/progression_rewards.py` extracts the existing threshold and attribute-budget
  semantics used by settlement and regional claims; it does not define a second XP
  curve.
- `game/pve_live.py`, `game/pve_reward_settlement.py`, `game/enemy_profiles.py`, and
  `game/locations.py` add the exact special/mixed/service rows while retaining normal
  spawn slots and existing reservation, recovery, reward, hunt, and harvest rules.
- `handlers/regional.py`, `handlers/chapter.py`, and `handlers/location.py` expose six
  peer Journal views, complete regional summaries, nearby actions, bounded pages,
  token-bound previews, source state, and existing map/profession/equipment routes.
- `locales/rav1_{ru,en,es}.py` and location locale maps own all new player-facing copy.

The migration adds exactly `rav1_projects`, `rav1_facts`, `rav1_claims`,
`rav1_combat_bindings`, and `rav1_pins`, plus the existing shared migration marker.
No RAV table replaces hunt, profession, settlement, inventory, travel, or build data.

## Transaction and compatibility guarantees

Finite and repeat mutations consume versioned UI actions under `BEGIN IMMEDIATE`,
perform inventory/progression/state changes, write the durable economy receipt, and
commit as one unit. Receipt-first replay recovers a committed result even after
location or travel revision changes. Failure before receipt rolls back entitlement,
goods, progress, and reward; response loss after commit recovers the exact result.

Craft progress is recorded in the existing successful craft transaction and ignores
pre-acceptance crafts and receipt replay. Combat bindings are frozen from the active
project step and exact roster at runtime start. Settlement T2 consumes those bindings
once; late acceptance, defeated/fled participants, corrupt/missing bindings, or an
unknown catalogue version cannot manufacture credit.

The migration and focused regression matrices preserve existing player, inventory,
gear, Chapter I, hunt, profession, recipe, travel, build, mastery, receipt, and PvE
state. The RAV startup path does not backfill facts, projects, claims, or kill credit.

## Rewards and economy

All ten finite entitlements total exactly 440 XP, 201 gold, two enhancement shards,
three small health potions, and one field ration. Choice outcomes have identical
numeric rewards. Findings grant nothing. The three standing batches pay exactly
10/20/12 gold and zero character, mastery, profession, or hunter XP. Their payouts
remain no greater than submitted-output resale and recursively expanded raw resale;
tests also reject a vendor or alternate-recipe cycle.

## Executable evidence

The focused RAV invariant matrix passed 37 tests in 7.22 seconds at `4f38f20`.
The earned production journey module defines exactly J01–J20 and passed all 25
collected parameter runs in 41.38 seconds when cloning the recorded legal checkpoint.
The source checkpoint was first produced by the full PEV1 registration, Chapter I,
travel, gathering, crafting, hunt, combat, gear, and profession history in 369.39
seconds. Its SHA-256 is
`7EE968B9861312799D743FAF87D6AFC3F9D099640B06E68E7E94F8CAFDAC9E6C`.
No project, fact, claim, reward, material, level, combat outcome, or receipt was edited
into the checkpoint.

The affected existing crafting, progression, settlement, open-world PvE, Journal, and
location regression matrix passed 156 tests except for one deliberately stale keyboard
expectation; the exact corrected node then passed. The final broad suite result and
log reference are populated in the machine evidence after the single candidate run.

See [regional_adventures_v1.json](../evidence/regional_adventures_v1.json) for commands,
case IDs, provenance, source identifiers, assertions, and result counts. Fixture-built
schema/corruption tests are labelled unit/integration evidence and are not represented
as production acquisition.

## Review, limitations, and state

No frozen-contract contradiction or product redesign was introduced. Contract
non-goals remain excluded. Durable receipts and permanent facts/claims intentionally
have no pruning in V1. Shared named/mixed sources can be busy or respawning by design;
the UI exposes that state and alternate activity links.

Independent review of the exact final candidate remains a separate required workflow
step and is not self-certified by this implementation report. Human validation has
not run; the three-session plan is recorded separately and the candidate is not
described as fully playtested or alpha validated.

Merge, deployment, live-account operation, independent approval, and human validation
are distinct. This report records an unmerged Draft candidate only.
