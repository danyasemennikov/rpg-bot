"""Twelve deterministic guild examinations; proof is a newly committed action."""
import json
import secrets
import time
from dataclasses import asdict
from game.action_receipts import ActionRejected, peaceful_player
from game.profession_state import get_state, award_operation, write_progression
from game.profession_progression import ProfessionProgression, work_xp
from game.profession_schema import GATHERING_PROFESSION_KEYS
from game.profession_resources import RESOURCES
from game.profession_recipes import get_recipe
from game.recipe_knowledge import require_knowledge, knowledge_spec

EXAM_SOURCES = {
    'woodcutting':('wood_common','frostpine_wood','wood_dark'),
    'mining':('iron_ore','gem_common','stone_chunk'),
    'herbalism':('herb_common','shore_herbs','marsh_herb'),
    'fishing':('shore_fish','marsh_fish','oasis_fish'),
    'hunting':('wolf_pelt','spider_silk','boar_meat'),
    'blacksmith':('pe_sword_1h_01','pxe_tool_mining_1','pe_sword_1h_01'),
    'arcane_engineer':('pe_wand_01','pxe_tool_fishing_1','pe_wand_01'),
    'heavy_armor':('pe_heavy_chest_01','a25_H_01','a25_H_01'),
    'medium_armor':('trail_vest','a25_M_01','a25_M_01'),
    'light_armor':('pe_light_chest_01','a25_L_01','a25_L_01'),
    'alchemy':('field_tonic','field_mana','field_tonic'),
    'cooking':('trail_ration','pe_cooking_shore_01','pe_cooking_shore_01'),
}
CRITERIA=('a','b','sample')


def _writer(conn):
    if not conn.in_transaction:
        raise RuntimeError('exam action requires caller-owned writer transaction')


def get_exam(conn,player_id,exam_id):
    row=conn.execute('SELECT * FROM profession_exam WHERE exam_id=? AND player_id=?',(exam_id,player_id)).fetchone()
    if not row:
        raise ActionRejected('exam_not_found')
    return dict(row)


def register_exam(conn,player_id,profession,*,now_ms=None):
    _writer(conn)
    peaceful_player(conn,player_id,service='craftsmen_guild')
    state=get_state(conn,player_id,profession,registered=True)
    old=conn.execute('SELECT * FROM profession_exam WHERE player_id=? AND profession_key=? AND target_tier=2',
                     (player_id,profession)).fetchone()
    if old:
        return dict(old)
    if state['level']!=15:
        raise ActionRejected('exam_requires_p15')
    gathering=profession in GATHERING_PROFESSION_KEYS
    plan={}
    for criterion,source in zip(CRITERIA,EXAM_SOURCES[profession]):
        if gathering:
            resource=RESOURCES[source]
            snapshot={'item_id':source,'tier':resource.resource_tier,'category':resource.work_category}
        else:
            snapshot=asdict(get_recipe(source))
        plan[criterion]={'source_id':source,'snapshot':snapshot,'policy_version':3}
    exam_id=secrets.token_hex(16)
    conn.execute('''INSERT INTO profession_exam(exam_id,player_id,profession_key,target_tier,registered_ms,plan_json,status)
        VALUES (?,?,?,2,?,?,'registered')''',
        (exam_id,player_id,profession,int(time.time()*1000) if now_ms is None else now_ms,json.dumps(plan,sort_keys=True)))
    return get_exam(conn,player_id,exam_id)


def validate_exam_craft_context(conn,player_id,exam_id,recipe_id,operation_id,input_ref):
    exam=get_exam(conn,player_id,exam_id)
    if exam['status']!='registered':
        raise ActionRejected('invalid_input_authority')
    matching=[c for c in CRITERIA if operation_id==f'exam:{exam_id}:{c}']
    if len(matching)!=1:
        raise ActionRejected('invalid_input_authority')
    criterion=matching[0]
    stage=json.loads(exam['plan_json'])[criterion]
    if stage['source_id']!=recipe_id or input_ref!='input:'+operation_id:
        raise ActionRejected('invalid_input_authority')
    return stage['snapshot']


def perform_exam_action(conn,player_id,exam_id,criterion,*,expected_revision,now_ms=None):
    _writer(conn)
    exam=get_exam(conn,player_id,exam_id)
    if criterion not in CRITERIA:
        raise ActionRejected('invalid_exam_criterion')
    prior=conn.execute('''SELECT o.result_json FROM profession_exam_proof p
        JOIN profession_operation_receipts o ON o.operation_id=p.operation_id
        WHERE p.exam_id=? AND p.criterion=?''',(exam_id,criterion)).fetchone()
    if prior:
        return json.loads(prior['result_json'])
    peaceful_player(conn,player_id,service='craftsmen_guild')
    state=get_state(conn,player_id,exam['profession_key'],registered=True)
    if state['level']!=15 or exam['status']!='registered' or exam['revision']!=expected_revision:
        raise ActionRejected('stale_action')
    proofs={r['criterion'] for r in conn.execute('SELECT criterion FROM profession_exam_proof WHERE exam_id=?',(exam_id,))}
    if criterion=='sample' and not {'a','b'}<=proofs:
        raise ActionRejected('exam_practices_incomplete')
    stage=json.loads(exam['plan_json'])[criterion]
    source=stage['source_id']
    operation_id=f'exam:{exam_id}:{criterion}'
    input_ref='input:'+operation_id
    gathering=exam['profession_key'] in GATHERING_PROFESSION_KEYS
    require_knowledge(conn,player_id,exam['profession_key'],1,None if gathering else source)
    contents={'source_id':source,'loan_tool_tier':1} if gathering else dict(stage['snapshot']['requirements'])
    conn.execute("INSERT INTO guild_escrow VALUES (?,?, 'exam',?,'exam','input',?,'reserved')",
                 (input_ref,player_id,exam_id,json.dumps(contents,sort_keys=True)))
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    if now_ms<exam['registered_ms']:
        raise ActionRejected('invalid_exam_time')
    if gathering:
        conn.execute("UPDATE guild_escrow SET status='consumed' WHERE escrow_id=?",(input_ref,))
        output_ref='output:'+operation_id
        conn.execute("INSERT INTO guild_escrow VALUES (?,?, 'exam',?,'exam','output',?,'reserved')",
                     (output_ref,player_id,exam_id,json.dumps({'item_id':source,'quantity':1})))
        result=award_operation(conn,player_id,exam['profession_key'],operation_id=operation_id,
            mode='profession_exam',source_id=source,context_id=exam_id,
            attempted=work_xp(gathering=True,work_tier=1,category=stage['snapshot']['category'],current_level=15),
            result={'exam_id':exam_id,'criterion':criterion,'output_escrow_ref':output_ref},now_ms=now_ms)
    else:
        from game.crafting_runtime import execute_craft_operation
        craft=execute_craft_operation(conn,player_id,source,operation_id=operation_id,mode='profession_exam',
            context_id=exam_id,input_escrow_id=input_ref,now_ms=now_ms)
        output_ref=craft['output_escrow_ref']
        result=json.loads(conn.execute('SELECT result_json FROM profession_operation_receipts WHERE operation_id=?',
                                       (operation_id,)).fetchone()[0])
    conn.execute('INSERT INTO profession_exam_proof VALUES (?,?,?,?)',(exam_id,criterion,operation_id,output_ref))
    if criterion=='sample':
        conn.execute("UPDATE guild_escrow SET status='submitted' WHERE escrow_id=?",(output_ref,))
    conn.execute('UPDATE profession_exam SET revision=revision+1,status=? WHERE exam_id=?',
                 ('sample_submitted' if criterion=='sample' else 'registered',exam_id))
    return result


def confirm_exam(conn,player_id,exam_id,reward_knowledge_id,*,expected_revision):
    _writer(conn)
    exam=get_exam(conn,player_id,exam_id)
    if exam['status']=='confirmed':
        return json.loads(exam['result_json'])
    player=peaceful_player(conn,player_id,service='craftsmen_guild')
    state=get_state(conn,player_id,exam['profession_key'],registered=True)
    if exam['revision']!=expected_revision or exam['status']!='sample_submitted' or state['level']!=15:
        raise ActionRejected('exam_incomplete')
    plan=json.loads(exam['plan_json'])
    proofs=conn.execute('''SELECT p.criterion,p.operation_id,p.escrow_id,o.player_id,o.profession_key,
        o.origin_mode,o.context_id,o.source_id,o.committed_ms,e.owner,e.context_kind,e.context_id AS escrow_context,
        e.player_id AS escrow_player,e.status AS escrow_status
        FROM profession_exam_proof p JOIN profession_operation_receipts o ON o.operation_id=p.operation_id
        JOIN guild_escrow e ON e.escrow_id=p.escrow_id WHERE p.exam_id=?''',(exam_id,)).fetchall()
    if {r['criterion'] for r in proofs}!=set(CRITERIA) or len(proofs)!=3:
        raise ActionRejected('exam_incomplete')
    for proof in proofs:
        criterion=proof['criterion']
        if (proof['player_id']!=player_id or proof['escrow_player']!=player_id
                or proof['profession_key']!=exam['profession_key'] or proof['origin_mode']!='profession_exam'
                or proof['context_id']!=exam_id or proof['escrow_context']!=exam_id
                or proof['owner']!='exam' or proof['context_kind']!='exam'
                or proof['committed_ms']<exam['registered_ms'] or proof['source_id']!=plan[criterion]['source_id']
                or proof['operation_id']!=f'exam:{exam_id}:{criterion}'
                or proof['escrow_status']!=('submitted' if criterion=='sample' else 'reserved')):
            raise ActionRejected('invalid_exam_proof')
    reward=knowledge_spec(reward_knowledge_id)
    if not reward or reward['profession_key']!=exam['profession_key'] or reward['tier']!=2:
        raise ActionRejected('invalid_exam_reward')
    if conn.execute('SELECT 1 FROM player_recipe_knowledge WHERE player_id=? AND recipe_id=?',(player_id,reward_knowledge_id)).fetchone():
        raise ActionRejected('exam_reward_already_known')
    conn.execute("INSERT INTO player_recipe_knowledge(player_id,recipe_id,acquired_via,learned_location_id,gold_paid,catalog_version) VALUES (?,?,'exam',?,0,3)",
                 (player_id,reward_knowledge_id,player['location_id']))
    write_progression(conn,player_id,exam['profession_key'],ProfessionProgression(15,0,16,0,0))
    result={'status':'confirmed','exam_id':exam_id,'profession_key':exam['profession_key'],'level':16,'exp':0,
            'reward_knowledge_id':reward_knowledge_id,'title_key':'journeyman','journal_fact':'profession_tier_2',
            'gold_delta':0,'policy_version':3}
    # The unique, confirmed exam row is the professional certificate/journal fact.
    conn.execute("UPDATE profession_exam SET status='confirmed',revision=revision+1,reward_knowledge_id=?,result_json=? WHERE exam_id=?",
                 (reward_knowledge_id,json.dumps(result,sort_keys=True),exam_id))
    conn.execute("UPDATE guild_escrow SET status='closed' WHERE context_kind='exam' AND context_id=?",(exam_id,))
    return result
