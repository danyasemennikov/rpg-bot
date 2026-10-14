# Epic I — implementation owner / DDL map

Base: `36368178541510d0d6794117ef17843722c52846` (local and remote verified).
Contract SHA256: `1CA72DA8D4EA0127B9F8221CBE90C50AE0B158D29A60403D0F91DA4FFBFBD984`.
Authority: Issue #241 owner approval, comment 6179948884, plus current implementation request.
Status: implementation plan; no runtime acceptance claimed.

## Owners and consumers

| State | Sole writer / transaction owner | Consumers and changes |
|---|---|---|
| P/XP/registration | `profession_state.py` over existing crafting/gathering tables | `database.py`, `profession_schema.py`, `alpha_schema.py`, crafting, tools, field gathering, hunting; eliminate direct XP updates outside owner |
| Knowledge/vouchers | `recipe_knowledge.py` | Explicit registration and selected learning, no grandfather/starter automatic knowledge; 153 craft +20 manuals |
| Catalog/materials | `profession_recipes.py`, `profession_resources.py` | Exact V2.2 BOM, RL/tier/work separate; `items_data.py`, `seed.py`, handbook, gathering foundation |
| Operations/batch | `crafting_runtime.py` caller-owned connection executor | Personal singleton and batch share executor; guild/exam outputs go to escrow; observers only for personal adventure craft |
| Tool slot | `profession_tools.py` | U1–6, capacities90/150/210/240/300/360; personal installation/commission revision; NPC loan never in field slot |
| Guild job/escrow | `profession_guild.py` | 4 maker /15 gather stages; immutable accepted plan; explicit stages, claim/cancel; NPC stock and quotes |
| Exam/proof/title | `profession_exams.py` | 12 definitions, A/B/sample distinct operations; third sample may repeat A recipe; one atomic promotion and II choice |
| Activity | existing `player_activity.py` projection + writer transaction | Guild rows join travel/gather/combat projection; all starters and instant professional operations check same owner under BEGIN IMMEDIATE |
| Equipped instances | `gear_progression.py`, `gear_instances.py` | Normal/ring/compare/legacy/starter/setters all call `equip_requirements.py` |
| Retention | `tier_advancement.py`, `gear_progression.py`, `build_progression.py` | Future T/prospective permanent stats; atomic auto-unequip/cost/revision/resource clamp; actor snapshot normalization |
| Consumable effects | existing item-use/evaluator and snapshot owners | 12 effects, one food/preparation slot, duration/settlement; no PvP allowlist expansion |
| Telegram UI | profession/recipe/inventory/location/activity handlers, `bot.py` routing | Mentor/jobs/exams/material supply/quotes/batch/retry/requirements; RU/EN/ES |

All gameplay mutations use a caller-owned writer transaction. Existing `economy_action_receipts` remains the request/result authority; operation receipts below own individual XP facts. No second writable copy of P/XP is added. Tier is derived from P (1..15 => I,16..30 => II), with eight ranges represented as policy metadata.

## Exact DDL design

The fresh crafting and gathering tables retain their existing player-ID column names and primary keys. Both receive these columns/constraints at creation:

```sql
level INTEGER NOT NULL DEFAULT 1 CHECK(level BETWEEN 1 AND 30),
exp INTEGER NOT NULL DEFAULT 0 CHECK(exp>=0 AND (level NOT IN (15,30) OR exp=0)),
registered_at INTEGER,
revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0)
```

Existing profession-key CHECK lists remain exactly the seven crafting/five gathering keys. Gathering retains `updated_at`. A read-only `profession_state` UNION ALL view exposes player_id/profession_key/level/exp/registered_at/revision/tier. Bootstrap creates rows only, never registration or learning.

```sql
CREATE TABLE IF NOT EXISTS profession_vouchers (
 player_id INTEGER NOT NULL REFERENCES players(telegram_id),
 profession_key TEXT NOT NULL,
 slot INTEGER NOT NULL CHECK(slot IN (1,2)),
 knowledge_id TEXT, redeemed_ms INTEGER,
 PRIMARY KEY(player_id,profession_key,slot),
 CHECK((knowledge_id IS NULL)=(redeemed_ms IS NULL))
);
CREATE TABLE IF NOT EXISTS profession_operation_receipts (
 operation_id TEXT PRIMARY KEY,
 player_id INTEGER NOT NULL REFERENCES players(telegram_id),
 profession_key TEXT NOT NULL,
 origin_mode TEXT NOT NULL CHECK(origin_mode IN ('personal','paid_job','personal_processing','profession_exam')),
 source_id TEXT NOT NULL, context_id TEXT,
 attempted INTEGER NOT NULL CHECK(attempted>=0),
 applied INTEGER NOT NULL CHECK(applied>=0),
 discarded INTEGER NOT NULL CHECK(discarded>=0),
 policy_version INTEGER NOT NULL CHECK(policy_version=3),
 result_json TEXT NOT NULL, committed_ms INTEGER NOT NULL,
 CHECK(attempted=applied+discarded)
);
CREATE TABLE IF NOT EXISTS profession_batch (
 batch_id TEXT PRIMARY KEY,
 player_id INTEGER NOT NULL REFERENCES players(telegram_id),
 fingerprint TEXT NOT NULL, payload_json TEXT NOT NULL,
 result_json TEXT, created_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS profession_batch_child (
 batch_id TEXT NOT NULL REFERENCES profession_batch(batch_id),
 child_index INTEGER NOT NULL CHECK(child_index>=0),
 operation_id TEXT NOT NULL UNIQUE REFERENCES profession_operation_receipts(operation_id),
 PRIMARY KEY(batch_id,child_index)
);
CREATE TABLE IF NOT EXISTS guild_job (
 job_id TEXT PRIMARY KEY,
 player_id INTEGER NOT NULL REFERENCES players(telegram_id),
 profession_key TEXT NOT NULL,
 mode TEXT NOT NULL CHECK(mode IN ('paid_job','personal_processing')),
 status TEXT NOT NULL CHECK(status IN ('active','ready_to_claim','claimed','cancelled')),
 plan_json TEXT NOT NULL, fingerprint TEXT NOT NULL,
 accepted_ms INTEGER NOT NULL, next_stage_earliest_ms INTEGER NOT NULL,
 stage_cursor INTEGER NOT NULL DEFAULT 0 CHECK(stage_cursor>=0),
 revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
 terminal_result_json TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS guild_job_player_active ON guild_job(player_id)
 WHERE status IN ('active','ready_to_claim');
CREATE TABLE IF NOT EXISTS guild_stage_receipt (
 job_id TEXT NOT NULL REFERENCES guild_job(job_id),
 stage_index INTEGER NOT NULL CHECK(stage_index>=0),
 operation_id TEXT NOT NULL UNIQUE REFERENCES profession_operation_receipts(operation_id),
 committed_ms INTEGER NOT NULL,
 PRIMARY KEY(job_id,stage_index)
);
CREATE TABLE IF NOT EXISTS profession_exam (
 exam_id TEXT PRIMARY KEY,
 player_id INTEGER NOT NULL REFERENCES players(telegram_id),
 profession_key TEXT NOT NULL, target_tier INTEGER NOT NULL CHECK(target_tier=2),
 registered_ms INTEGER NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('registered','sample_submitted','confirmed')),
 revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
 reward_knowledge_id TEXT, result_json TEXT,
 UNIQUE(player_id,profession_key,target_tier)
);
CREATE TABLE IF NOT EXISTS guild_escrow (
 escrow_id TEXT PRIMARY KEY,
 player_id INTEGER NOT NULL REFERENCES players(telegram_id),
 context_kind TEXT NOT NULL CHECK(context_kind IN ('job','exam')),
 context_id TEXT NOT NULL,
 owner TEXT NOT NULL CHECK(owner IN ('npc','exam')),
 direction TEXT NOT NULL CHECK(direction IN ('input','output')),
 contents_json TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('reserved','consumed','submitted','closed'))
);
CREATE TABLE IF NOT EXISTS profession_exam_proof (
 exam_id TEXT NOT NULL REFERENCES profession_exam(exam_id),
 criterion TEXT NOT NULL CHECK(criterion IN ('a','b','sample')),
 operation_id TEXT NOT NULL UNIQUE REFERENCES profession_operation_receipts(operation_id),
 escrow_id TEXT NOT NULL UNIQUE REFERENCES guild_escrow(escrow_id),
 PRIMARY KEY(exam_id,criterion)
);
```

`player_recipe_knowledge` keeps its existing PK; allowed provenance becomes voucher/guild/exam/regional (no grandfather seed). Existing economy receipt schema is retained. U slots/session validators expand to1..6, capacity CHECK uses CASE over the six capacities. Field session120000ms constraint stays unchanged. Guild immutable `plan_json` stores tier/knowledge/stages/BOM/source/quote/wage/yield/mastery/policy/durations. Only cursor/deadline/revision/status are mutable. Jobs/exams reference escrow by context; operation and proof owners validate context and performer under writer lock. Exact generated SQLite DDL will be recorded and tested at checkpoint1.

## Checkpoints

1. schema/owners/progression/activity, fresh ensure/restart tests
2. catalog/knowledge/tools/NPC supply, full data closure
3. atomic craft/batch/modes/rollback
4. guild scheduler/economy/deadlines/cancel/restart
5. twelve exams/proof/choice races
6. every equip writer/retention/reset/snapshot
7. effects/UX/RU/EN/ES
8. exact-HEAD integration/journeys/economy evidence and independent Astra High review

One branch and one Draft PR throughout. No Telegram poller or working database execution. Tests use disposable clean databases. STATIC, UNIT/INTEGRATION, SIMULATED and REAL_TELEGRAM are reported separately.
