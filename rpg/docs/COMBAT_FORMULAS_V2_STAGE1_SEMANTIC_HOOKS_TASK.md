# Stage 1 Task for Codex — Semantic Hooks for Combat Formulas v2

## Status
This task is the first implementation step after Combat Core v1 stabilization.

The goal is **not** to rebalance the whole game yet.
The goal is to add the minimum semantic hooks needed for the future formulas / weapons / armor redesign.

This task must follow the repository workflow:
- ChatGPT defines architecture, balance, specs, and review direction.
- Codex implements approved changes.
- Do not assume any previous unmerged patches already exist.

---

## Required reading order
Before changing code, read in this order:
1. `AGENTS.md`
2. `CLAUDE.md`
3. `GAME_FOUNDATION.md`
4. `docs/COMBAT_CORE_V1_SPEC.md`
5. target files for this task

---

## Goal
Introduce new semantic combat/equipment fields so the project can later support:
- weapon-specific scaling profiles;
- armor classes;
- offhand roles;
- damage school separation;
- future anti-heavy-meta balancing through stat budgets / tempo cost instead of hard class locks.

This is a **structure-first** task.
It should expand the language of the system without forcing a full combat redesign in the same patch.

---

## Why this task exists
Current combat logic is already much more centralized in `game/combat.py`, and Combat Core v1 is considered stable enough to move into formulas work.

However, the current combat model still relies too much on coarse concepts like `weapon_type`, which is not enough to cleanly represent the intended archetypes from `GAME_FOUNDATION.md`.

Examples of profiles that must be distinguishable in the future:
- one-handed sword
- two-handed sword
- two-handed axe
- daggers
- bow
- magic staff
- holy staff
- wand
- holy rod
- shield / focus / censer style offhands

Without this semantic layer, future formulas would still be forced to balance unlike archetypes as if they were the same weapon family.

---

## Files to inspect
Minimum:
- `game/combat.py`
- `game/balance.py`
- `game/skill_engine.py`
- `game/items_data.py`
- `handlers/battle.py`
- `database.py` only if truly needed

Also inspect nearby code that reads equipped weapon data or battle state setup.

---

## Main constraints
1. **Do not** perform the full formulas rebalance in this task.
2. **Do not** redesign all weapons / skill trees / armor items in this task.
3. **Do not** move combat math back into handlers.
4. **Do not** break current cooldown flow or reward flow.
5. **Do not** replace the current `context.user_data['battle']` model.
6. Keep changes incremental and readable for a beginner-friendly codebase.
7. Preserve current gameplay behavior as much as possible unless a small compatibility shim is required.

---

## What must be added

### 1. Weapon profile support
Add support for a more specific field than the current coarse `weapon_type`.

Target concept:
- `weapon_profile`

Examples of valid values:
- `sword_1h`
- `sword_2h`
- `axe_2h`
- `daggers`
- `bow`
- `magic_staff`
- `holy_staff`
- `wand`
- `holy_rod`
- `unarmed`

Requirements:
- the battle state should be able to store `weapon_profile`;
- equipped weapon loading should expose `weapon_profile` if the item defines it;
- when missing, old items should fall back safely to a compatible default;
- current code using `weapon_type` must keep working.

### 2. Armor class support
Add a semantic concept for armor category.

Target concept:
- `armor_class`

Initial values:
- `light`
- `medium`
- `heavy`

Requirements:
- item definitions should be able to declare `armor_class`;
- if armor pieces are inspected/loaded in combat-related code, missing values should fall back safely;
- no balance changes are required yet;
- the field should be introduced in a way that future formulas can query it.

### 3. Offhand profile support
Add a semantic concept for offhand role.

Target concept:
- `offhand_profile`

Initial values can include:
- `none`
- `shield`
- `focus`
- `censer`
- `orb`
- `tome`

Requirements:
- item data should be able to define it;
- if the player has no offhand, the system should behave safely;
- no hard weapon↔offhand restrictions should be introduced in this task.

### 4. Damage school support
Add a semantic field for action / attack damage school.

Target concept:
- `damage_school`

Initial values:
- `physical`
- `ranged_physical`
- `arcane`
- `holy`

Requirements:
- add support in places where direct damage actions are assembled or resolved;
- preserve current behavior by mapping existing actions to a sane default school;
- do not redesign all skills yet, only make the system able to carry the semantic field.

### 5. Encumbrance hook
Add a lightweight future-facing hook for equipment heaviness.

Target concept:
- `encumbrance`

Requirements:
- this can initially live as optional item metadata or a derived helper;
- no real formulas need to use it yet;
- the system should simply become capable of storing/querying it later.

---

## Expected implementation style
Use the smallest coherent change set.

Good shape for this task:
- add optional metadata to item definitions;
- add helpers that normalize old/new item data;
- thread normalized values into battle state creation;
- thread `damage_school` through direct-damage flow where it is natural;
- keep compatibility with old code paths.

Avoid:
- giant rewrites;
- mass data migration unless clearly needed;
- introducing a new complex object model;
- rewriting battle state into classes/dataclasses unless absolutely necessary.

---

## Compatibility / fallback rules
Because the codebase already has existing items and battle flow, this task must be backward-compatible.

Suggested fallback behavior:
- if an equipped weapon has no `weapon_profile`, infer one from old `weapon_type` or item type;
- if armor has no `armor_class`, infer the safest current default or leave it `None` with helper normalization;
- if offhand has no `offhand_profile`, infer or default to `none`;
- if a damage action has no `damage_school`, map it from current action type;
- if `encumbrance` is absent, use a neutral default.

Important:
Backward compatibility should be handled in a few clear normalization helpers, not duplicated all over the code.

---

## Suggested helper approach
Codex may introduce small explicit helpers with readable names, for example:
- `normalize_weapon_profile(...)`
- `normalize_armor_class(...)`
- `normalize_offhand_profile(...)`
- `normalize_damage_school(...)`
- `get_item_encumbrance(...)`

Exact names may differ, but the intent should stay the same:
keep the compatibility logic centralized and easy to read.

---

## Non-goals for this task
The following are explicitly out of scope:
- full balance pass for `game/balance.py`;
- new damage formulas for every archetype;
- heavy armor penalties;
- redesign of all existing items;
- redesign of all skills;
- migration of all old content to perfect final profiles;
- battle UI rewrite;
- database schema rewrite unless absolutely required.

---

## Done criteria
This task is done when all of the following are true:

1. The codebase has a clear semantic concept of:
   - `weapon_profile`
   - `armor_class`
   - `offhand_profile`
   - `damage_school`
   - `encumbrance`

2. Existing battle flow still works without requiring a full content rewrite.

3. Existing items without the new fields do not crash combat and get sane fallback behavior.

4. Battle state / combat setup can carry enough information for future formulas work.

5. Direct-damage action flow can carry `damage_school` semantically, even if formulas do not fully use it yet.

6. The patch remains incremental, readable, and does not expand scope into full rebalance.

---

## Nice-to-have tests
If the current test layout makes it practical, add or update a few focused regression tests for:
- weapon without explicit `weapon_profile` still entering battle correctly;
- item with explicit `weapon_profile` preserving that profile in battle state;
- missing offhand safely defaulting to `none`;
- direct-damage action getting a stable default `damage_school`;
- no regressions in core combat regression tests.

Do not build a giant new test suite in this task.

---

## What Codex should report after implementation
In the final summary, report:
1. what semantic hooks were added;
2. which files changed;
3. how backward compatibility is handled;
4. whether any assumptions were made about current item schemas;
5. whether further formulas work can now begin safely.

---

## Follow-up task after this one
After this task is merged, the next task should be:
**Formula Pass v2**

That next task should focus on:
- scaling cleanup;
- crit/dodge/mitigation caps;
- offensive and defensive stat separation;
- armor impact on survivability/tempo;
- preparation for weapon-profile-specific formulas.
