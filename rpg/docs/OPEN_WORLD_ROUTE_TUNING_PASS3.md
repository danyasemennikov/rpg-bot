# Open-world Route Tuning Pass 3 (PR 3H)

This pass follows the readiness/reporting layers introduced in PR 3E and used in PR 3F/3G.

Scope is limited to:
- `route_ashen_ruins`
- `route_sunscar`
- `route_mireveil`

Route identity in this pass:
- Ashen Ruins are treated as the undead/ruins combat route.
- Sunscar is treated as the desert/badlands combat route.
- Mireveil is treated as the swamp/mire combat route.

Readiness goals for these non-stub major routes:
- solo mobs present;
- pack pressure present where current live route-local composition already supports it;
- elite anchors present;
- composition/report/validator layers remain aligned.

Rare anchors can remain deferred when current live route-local data does not yet represent them.

Out of scope in this pass:
- no reward number changes;
- no combat formula changes;
- no new mobs/content;
- no route topology changes;
- no blanket skill rollout;
- mixed-mob packs remain future work.

Current pass-3 route state note:
- `route_ashen_ruins` and `route_mireveil` currently satisfy pack-pressure readiness.
- `route_sunscar` currently retains a pack-pressure gap as a diagnostic warning (`no_pack_mobs_on_non_stub_route`) in this pass.
- Sunscar pack tuning is deferred to a future focused content pass rather than forcing unsafe content or pack-policy changes here.
