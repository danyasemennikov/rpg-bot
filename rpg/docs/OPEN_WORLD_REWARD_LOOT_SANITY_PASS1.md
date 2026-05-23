# OPEN_WORLD_REWARD_LOOT_SANITY_PASS1 (PR 3L)

This pass follows PR 3K combat numeric tuning and is the first explicit open-world reward + loot sanity pass.

Primary route scope:
- route_westwild
- route_frostspine
- route_ashen_ruins
- route_mireveil

Additional handling:
- route_sunscar excluded from pack-ready reward tuning because the pack-pressure gap (`no_pack_mobs_on_non_stub_route`) is still actionable.
- route_south_coast_stub and route_old_mine_stub remain smoke/sanity only.

Reward fields inspected/tuned:
- exp_reward
- gold_min
- gold_max
- loot_table

Explicit reward changes in this pass:
- mountain_stone_golem: exp_reward 60 -> 110, gold 3-9 -> 5-14.
- drowned: exp_reward 70 -> 105, gold 3-10 -> 5-14.

Intent:
- lift under-rewarded elite anchors so they are not worse than ordinary route solo ceilings;
- keep starter/moderate routes stable without inflating Westwild early progression;
- retain existing item ids and loot system shape.

Non-goals and unchanged boundaries:
- no combat formula changes
- no mob combat stat changes
- no reward formula changes
- no reward formula/global economy rewrite
- no item/drop economy architecture changes
- no new mobs
- no new items
- no spawn probability changes
- no route topology changes
- no skill targeting rollout changes
- no mixed-mob packs
- no PvP behavior changes
- no UI/repositioning
