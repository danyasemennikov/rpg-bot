import json
import os
import sqlite3

import database
from game.gear_instances import grant_item_to_player
from game.pve_live import _ensure_pve_encounter_table, _ensure_world_spawn_table
from game.pve_reward_settlement import recover_prepared_settlements
from game.profession_schema import CRAFTING_PROFESSION_KEYS, MIGRATION_VERSION, ensure_profession_schema


def _replace_with_frozen_baseline(conn):
    conn.execute('DROP TABLE player_crafting_professions')
    conn.execute('''CREATE TABLE player_crafting_professions (
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        profession_key TEXT NOT NULL CHECK (profession_key IN
            ('alchemy', 'cooking', 'medium_armor')),
        level INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 20),
        exp INTEGER NOT NULL DEFAULT 0 CHECK (exp >= 0),
        PRIMARY KEY (player_id, profession_key)
    )''')


def test_migration_preserves_rows_and_is_idempotent(tmp_path, monkeypatch):
    path = tmp_path / 'game.db'; monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    conn = database.get_connection()
    conn.execute("INSERT INTO players(telegram_id,name) VALUES (1,'old')")
    conn.execute("INSERT INTO player_crafting_professions(player_id,profession_key,level,exp) VALUES (1,'alchemy',7,321)")
    conn.execute("DELETE FROM economy_schema_migrations WHERE version=?", (MIGRATION_VERSION,))
    conn.commit()
    # Already-wide unmarked recovery preserves exact state and completes the marker.
    from game.profession_schema import ensure_profession_schema
    conn.execute('BEGIN IMMEDIATE'); ensure_profession_schema(conn); conn.commit()
    assert tuple(conn.execute("SELECT level,exp FROM player_crafting_professions WHERE player_id=1 AND profession_key='alchemy'").fetchone()) == (7,321)
    assert {r['profession_key'] for r in conn.execute('SELECT profession_key FROM player_crafting_professions WHERE player_id=1')} == set(CRAFTING_PROFESSION_KEYS)
    before = conn.total_changes; conn.execute('BEGIN IMMEDIATE'); ensure_profession_schema(conn); conn.commit()
    assert conn.execute('SELECT COUNT(*) c FROM economy_schema_migrations WHERE version=?',(MIGRATION_VERSION,)).fetchone()['c'] == 1
    conn.close()


def test_real_frozen_schema_migrates_losslessly_and_survives_restart(tmp_path, monkeypatch):
    path = tmp_path / 'game.db'; monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    from game.seed import seed_items
    seed_items()
    conn = database.get_connection()
    conn.execute("INSERT INTO players(telegram_id,name) VALUES (11,'old')")
    conn.execute("INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (11,'herb_common',9)")
    grant = grant_item_to_player(11, 'field_sword_1h', 1, source='test_fixture',
        gear_spec={'base_item_id':'field_sword_1h','item_tier':5,'rarity':'epic',
                   'secondary_rolls':[{'stat':'strength','value':7},
                                      {'stat':'vitality','value':5},
                                      {'stat':'accuracy','value':9}],
                   'enhance_level':3,'durability':77,'max_durability':91},
        provenance={'source':'test_fixture','marker':'preserve'}, conn=conn)
    conn.execute("INSERT INTO player_contract_history(player_id,contract_key) VALUES (11,'chapter_homecoming')")
    conn.execute("INSERT INTO player_contract_objectives(player_id,contract_key,objective_key,progress) VALUES (11,'chapter_homecoming','craft_field_tonic',3)")
    conn.commit(); conn.close()
    _ensure_pve_encounter_table(); _ensure_world_spawn_table()
    conn = database.get_connection()
    conn.execute('''INSERT INTO pve_encounters
        (encounter_id,owner_player_id,status,mob_id,battle_state_json,mob_json,finished_at,location_id)
        VALUES ('prepared-migration',11,'resolving_victory','forest_boar','{}','{}',CURRENT_TIMESTAMP,'westwild_n2')''')
    prepared_plan = {
        'schema_version': 1, 'policy_version': 'field_loot_v1',
        'encounter_id': 'prepared-migration', 'owner_player_id': 11,
        'location_id': 'westwild_n2', 'route_id': None,
        'eligible_recipient_ids': [11], 'defeated_participant_ids': [],
        'recipients': [], 'mastery_awards': [], 'enemy_units': [],
    }
    conn.execute('''INSERT INTO pve_reward_settlements
        (encounter_id,schema_version,policy_version,status,plan_json,result_json)
        VALUES ('prepared-migration',1,'field_loot_v1','prepared',?,'{}')''',
        (json.dumps(prepared_plan),))
    _replace_with_frozen_baseline(conn)
    conn.execute("INSERT INTO player_crafting_professions VALUES (11,'alchemy',20,777)")
    conn.execute("INSERT INTO player_gathering_professions(telegram_id,profession_key,level,exp) VALUES (11,'herbalism',8,123)")
    conn.execute("DELETE FROM economy_schema_migrations WHERE version=?", (MIGRATION_VERSION,))
    conn.commit()
    gear_before = dict(conn.execute('SELECT * FROM gear_instances WHERE id=?', (grant['instance_ids'][0],)).fetchone())
    chapter_before = dict(conn.execute("SELECT * FROM player_contract_objectives WHERE player_id=11").fetchone())
    settlement_before = dict(conn.execute("SELECT * FROM pve_reward_settlements WHERE encounter_id='prepared-migration'").fetchone())

    conn.execute('BEGIN IMMEDIATE'); ensure_profession_schema(conn); conn.commit()
    assert tuple(conn.execute("SELECT level,exp FROM player_crafting_professions WHERE player_id=11 AND profession_key='alchemy'").fetchone()) == (20, 777)
    assert tuple(conn.execute("SELECT level,exp FROM player_gathering_professions WHERE telegram_id=11 AND profession_key='herbalism'").fetchone()) == (8, 123)
    assert conn.execute("SELECT quantity FROM inventory WHERE telegram_id=11 AND item_id='herb_common'").fetchone()['quantity'] == 9
    assert dict(conn.execute('SELECT * FROM gear_instances WHERE id=?', (grant['instance_ids'][0],)).fetchone()) == gear_before
    assert dict(conn.execute("SELECT * FROM player_contract_objectives WHERE player_id=11").fetchone()) == chapter_before
    assert dict(conn.execute("SELECT * FROM pve_reward_settlements WHERE encounter_id='prepared-migration'").fetchone()) == settlement_before
    conn.close()
    database.init_db()
    recovered = recover_prepared_settlements()
    assert len(recovered) == 1 and recovered[0]['status'] == 'applied'
    conn = database.get_connection()
    assert tuple(conn.execute("SELECT level,exp FROM player_crafting_professions WHERE player_id=11 AND profession_key='alchemy'").fetchone()) == (20, 777)
    settlement = conn.execute("SELECT status,result_json FROM pve_reward_settlements WHERE encounter_id='prepared-migration'").fetchone()
    assert settlement['status'] == 'applied' and 'prepared-migration' in settlement['result_json']
    conn.close()


def test_migration_rolls_back_and_keeps_unexpected_temp_table(tmp_path, monkeypatch):
    path = tmp_path / 'game.db'; monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    conn = database.get_connection()
    conn.execute("INSERT INTO players(telegram_id,name) VALUES (12,'old')")
    _replace_with_frozen_baseline(conn)
    conn.execute("INSERT INTO player_crafting_professions VALUES (12,'alchemy',4,91)")
    conn.execute("CREATE TABLE player_crafting_professions_pev1_new(sentinel TEXT)")
    conn.execute("INSERT INTO player_crafting_professions_pev1_new VALUES ('keep')")
    conn.execute("DELETE FROM economy_schema_migrations WHERE version=?", (MIGRATION_VERSION,))
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    try:
        ensure_profession_schema(conn)
    except RuntimeError:
        conn.rollback()
    else:
        raise AssertionError('unexpected temporary table must fail closed')
    assert conn.execute("SELECT sentinel FROM player_crafting_professions_pev1_new").fetchone()['sentinel'] == 'keep'
    assert tuple(conn.execute("SELECT level,exp FROM player_crafting_professions WHERE player_id=12").fetchone()) == (4, 91)
    assert conn.execute("SELECT COUNT(*) c FROM economy_schema_migrations WHERE version=?", (MIGRATION_VERSION,)).fetchone()['c'] == 0
    conn.close()


def test_migration_rejects_structurally_incompatible_schema(tmp_path, monkeypatch):
    path = tmp_path / 'game.db'; monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    conn = database.get_connection()
    conn.execute("DELETE FROM economy_schema_migrations WHERE version=?", (MIGRATION_VERSION,))
    conn.execute("CREATE INDEX unexpected_profession_index ON player_crafting_professions(level)")
    conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    try:
        ensure_profession_schema(conn)
    except RuntimeError as exc:
        assert 'unexpected player_crafting_professions schema' in str(exc)
        conn.rollback()
    else:
        raise AssertionError('incompatible schema must fail closed')
    conn.close()


def test_exception_after_rebuild_rolls_back_all_migration_ddl_and_rows(tmp_path, monkeypatch):
    path = tmp_path / 'game.db'; monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    conn = database.get_connection()
    conn.execute("INSERT INTO players(telegram_id,name) VALUES (13,'old')")
    _replace_with_frozen_baseline(conn)
    conn.execute("INSERT INTO player_crafting_professions VALUES (13,'cooking',9,456)")
    conn.execute("DELETE FROM economy_schema_migrations WHERE version=?", (MIGRATION_VERSION,))
    conn.commit()
    import game.profession_schema as schema
    monkeypatch.setattr(schema, 'ensure_profession_rows', lambda *_: (_ for _ in ()).throw(RuntimeError('forced failure')))
    conn.execute('BEGIN IMMEDIATE')
    try:
        schema.ensure_profession_schema(conn)
    except RuntimeError as exc:
        assert str(exc) == 'forced failure'
        conn.rollback()
    else:
        raise AssertionError('forced failure must escape the migration')
    assert tuple(conn.execute("SELECT profession_key,level,exp FROM player_crafting_professions").fetchone()) == ('cooking', 9, 456)
    assert "'heavy_armor'" not in conn.execute("SELECT sql FROM sqlite_master WHERE name='player_crafting_professions'").fetchone()['sql']
    assert conn.execute("SELECT COUNT(*) c FROM economy_schema_migrations WHERE version=?", (MIGRATION_VERSION,)).fetchone()['c'] == 0
    assert conn.execute("SELECT COUNT(*) c FROM sqlite_master WHERE name='player_crafting_professions_pev1_new'").fetchone()['c'] == 0
    conn.close()
