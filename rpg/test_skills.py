import sys
sys.path.append('/workspaces/rpg-bot')

from game.skills import SKILLS, SKILL_TREES

print('\n' + '='*50)
print('ДЕРЕВЬЯ ОРУЖИЯ И СКИЛЛЫ')
print('='*50)

for weapon_id, branches in SKILL_TREES.items():
    print(f'\n🗡️  {weapon_id.upper()}')
    for branch, skill_ids in branches.items():
        print(f'  Ветка {branch}:')
        for skill_id in skill_ids:
            skill = SKILLS.get(skill_id)
            if skill:
                print(f'    [{skill["type"]:8}] {skill_id:25} — {skill["name"]}')
            else:
                print(f'    [MISSING ] {skill_id}')

print('\n' + '='*50)
print(f'Всего скиллов: {len(SKILLS)}')
print('='*50)