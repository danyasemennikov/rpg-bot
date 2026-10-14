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
