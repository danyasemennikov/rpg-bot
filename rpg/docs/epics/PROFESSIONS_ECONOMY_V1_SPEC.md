# Professions & Economy V1 — frozen implementation contract

This repository copy preserves the PEV1-1 Stage 3 contract and Producer clarifications used for implementation.

## Producer clarifications for Stage 3

### Clarification 1 — recovery / food items reuse the existing consumable runtime

All eight new recovery/food outputs must reuse the existing consumable system.

For every new recovery item:

- `item_type = 'potion'`
- healing/mana authority remains `stat_bonus_json` using:
  - `heal`
  - `mana`
- mixed food may contain both
- `consumable_family='food'` is additional metadata only
- do **not** create a new `food` item type
- do **not** create a second consumption engine
- reuse existing out-of-battle and battle consumption paths, caps, and turn costs

This resolves ambiguity around wording such as “heal/mana fields” in the contract.

### Clarification 2 — single environmental source authority

Do not maintain two independent handwritten environmental gathering source catalogs.

The exact location/chance table in PEV1-1 is authoritative content, but implementation must have **one runtime authority** for environmental placement/chances.

Other layers such as:

- `profession_resources.py`
- resource handbook
- validation
- reverse indexes
- tests

must derive from or validate that runtime authority rather than duplicate a second manually maintained set of location/chance values.

Harvest manifests and recipe-consumer indexes may keep their own appropriate authorities.

Environmental location/chance data must not drift between modules.

---

# Stage 2 — Frozen Contract PEV1-1

The complete section below is normative for implementation.

**Stage 2 is frozen as contract `PEV1-1`, ready for owner/Producer review.** This is a design specification, not an implementation or acceptance report. Main was rechecked and still matches the requested baseline. No files, branches, PRs, migrations, gameplay, tests, or evidence artifacts were created or changed.

**A. Verified baseline**

Repository: `danyasemennikov/rpg-bot`
Frozen and verified `main`: `27347ece2b17108a1aed1f6eb01f2a395480e6c9`.

The accepted Stage 1 findings remain applicable. Additional static inspection confirms:

- Crafting persistence still permits only `alchemy`, `cooking`, and `medium_armor`.
- Four recipes are live; four older definitions have a separate, weaker execution path.
- Ordinary equipment crafting can currently enter generic rarity generation.
- The applied PvE settlement contains `eligible_recipient_ids`, `defeated_participant_ids`, and the saved enemy roster needed for authoritative harvesting.
- Gathering already uses one transaction for delivery, XP, and objectives, but its request ledger does not retain results.
- Current inn and direct-gift code need narrow conservation fixes.
- PR232’s documentation structure is present, while current-state reconciliation still names the preceding baseline.

Static authorities: [crafting runtime](https://github.com/danyasemennikov/rpg-bot/blob/27347ece2b17108a1aed1f6eb01f2a395480e6c9/rpg/game/crafting_runtime.py), [profession schema](https://github.com/danyasemennikov/rpg-bot/blob/27347ece2b17108a1aed1f6eb01f2a395480e6c9/rpg/game/alpha_schema.py), [PvE settlement](https://github.com/danyasemennikov/rpg-bot/blob/27347ece2b17108a1aed1f6eb01f2a395480e6c9/rpg/game/pve_reward_settlement.py), [gear delivery](https://github.com/danyasemennikov/rpg-bot/blob/27347ece2b17108a1aed1f6eb01f2a395480e6c9/rpg/game/gear_instances.py), and [current-state documentation](https://github.com/danyasemennikov/rpg-bot/blob/27347ece2b17108a1aed1f6eb01f2a395480e6c9/rpg/docs/PROJECT_STATE_CURRENT.md).

**B. Frozen product contract**

V1 contains:

- All five gathering and seven crafting professions, without profession limits.
- Profession levels 1–20.
- **63 live recipes:** 30 weapons, nine offhands, 12 armor recipes, six alchemy recipes, and six cooking recipes.
- **28 mandatory material IDs**, including five new materials.
- **Eight new recovery consumables.**
- No new equipment templates.
- Permanent recipe knowledge and deterministic guild learning.
- Explicit crafted equipment tiers and common/uncommon rarity.
- Owner-only supplementary hunting.
- Durable economic result receipts.
- Paginated, fully localized profession navigation.

The 63 recipes comprise **17 starter recipes, eight level-6 recipes, 19 level-12 recipes, and 19 level-18 recipes**.

All learning and crafting occur at any existing craftsmen’s guild:

`capital_city`, `hub_westwild`, `hub_frostspine`, `hub_ashen_ruins`, `hub_mireveil`, `hub_sunscar`.

There are **no regional learning restrictions**. Regional identity comes from materials and production sources. Aster and Elmor introduce the system; learning never requires repeated regional commuting.

No new gathering cooldown, stamina, depletion, tool requirement, crafting fee, or intermediate manufacturing chain is introduced.

**C. Profession progression matrix**

All professions use the existing level threshold:

\\[ XP\_{\text{next}}(L)=50L,\qquad 1\leq L<20 \\]

Thus cumulative XP from level 1 is 750 at level 6, 3,300 at level 12, 7,650 at level 18, and 9,500 at level 20.

The numerical threshold is explicitly shared. **Gathering and crafting award policies are separate.**

| KeyDisplay identity: ru / en / esPersistenceMeaningful milestones and role |                                                                                    |                          |                                                                                                               |
| -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------- |
| `herbalism`                                                                | Травничество / Herbalism / Herboristería                                           | Existing gathering table | L1 common herbs, reeds and coastal plants; L6 marsh herbs; L8 magic herbs; L12 desert plants; L18 toxic herbs |
| `woodcutting`                                                              | Лесозаготовка / Woodcutting / Tala                                                 | Existing gathering table | L1 common wood; L6 dark wood; L12 frostpine; L18 ancient bark                                                 |
| `mining`                                                                   | Горное дело / Mining / Minería                                                     | Existing gathering table | L1 iron, coal and stone; L6 salt; L12 gems; L18 Sunscar ore                                                   |
| `fishing`                                                                  | Рыболовство / Fishing / Pesca                                                      | Existing gathering table | L1 coastal fish; L6 marsh fish; L12 oasis fish; L18 deep-marsh fish                                           |
| `hunting`                                                                  | Охота / Hunting / Caza                                                             | Existing gathering table | L1 meat/pelts; L2 fangs; L6 silk; L12 bear hides; L18 troll sinew                                             |
| `heavy_armor`                                                              | Изготовление тяжёлой брони / Heavy armor crafting / Fabricación de armadura pesada | Rebuilt crafting table   | L1 chest; L6 helmet; L12 legs; L18 chest project                                                              |
| `medium_armor`                                                             | Изготовление средней брони / Medium armor crafting / Fabricación de armadura media | Rebuilt crafting table   | Existing L1 vest; L6 helmet; L12 legs; L18 chest project                                                      |
| `light_armor`                                                              | Изготовление лёгкой брони / Light armor crafting / Fabricación de armadura ligera  | Rebuilt crafting table   | L1 chest; L6 helmet; L12 legs; L18 chest project                                                              |
| `blacksmith`                                                               | Кузнечное дело / Blacksmithing / Herrería                                          | Rebuilt crafting table   | Four metallic weapon families at L1/12/18; shields at L6/12/18                                                |
| `arcane_engineer`                                                          | Магическая инженерия / Arcane engineering / Ingeniería arcana                      | Rebuilt crafting table   | Six ranged/magical weapon families at L1/12/18; focus/censer at L6/12/18                                      |
| `alchemy`                                                                  | Алхимия / Alchemy / Alquimia                                                       | Rebuilt crafting table   | HP30 at L1; MP50 at L2; HP80 at L6; MP100 at L12; HP150/MP160 at L18                                          |
| `cooking`                                                                  | Кулинария / Cooking / Cocina                                                       | Rebuilt crafting table   | Meat and coastal food at L1; marsh food at L6; meat/oasis meals at L12; combined late-alpha meal at L18       |

Gathering XP:

```
r = explicit required profession level of the successfully delivered resource
gap = current_level - r
base = 8 + 2*r

current_level == 20: 0 XP
gap <= 4:           base XP
gap == 5:           floor(base / 2) XP
gap >= 6:           0 XP
```

Failed, empty, locked, rejected, and replayed actions award no new XP. Ordinary combat loot does not award hunting XP.

Crafting XP:

```
Recipe level 1 or 2: training ceiling 6
Recipe level 6:      training ceiling 12
Recipe level 12:     training ceiling 18
Recipe level 18:     training ceiling 20

If current_level >= training ceiling:
    award 0
Otherwise:
    remaining = sum(50*k for k in range(current_level, ceiling)) - current_exp
    award = min(250 * recipe_required_level, max(0, remaining))
```

This deliberately makes crafting progression depend on completing useful milestone projects. Starting at level 1 with zero XP, an ordinary L1 → L6 → L12 → L18 recipe path takes **3 + 2 + 2 + 1 successful crafts** to reach level 20. The existing L2 mana recipe can reach the first ceiling in two crafts.

There is no first-craft bonus, discovery ledger, training currency, or XP for learning/selling.

Successful progression may cross multiple levels. Reaching level 20 through new XP sets XP to zero. Migration and read-only views must never normalize or overwrite stored historical XP, including unusual existing cap rows. Zero-XP actions must not rewrite progression.

**D. Resource/source manifest**

The following aliases are used only to keep the recipe tables readable. Implementation stores the full `item_id`.

`H` = heavy armor, `M` = medium armor, `L` = light armor, `B` = blacksmith, `E` = arcane engineer, `A` = alchemy, `C` = cooking.

All existing quantities and item IDs are preserved. Existing material sale prices remain unchanged. New materials have `item_type=material`, `buy_price=0`, weight 1, and no vendor offer.

| Alias`item_id`ru / en / es identityProfession / levelClassificationSellConsumers |                           |                                                                                  |                |                        |    |         |
| -------------------------------------------------------------------------------- | ------------------------- | -------------------------------------------------------------------------------- | -------------- | ---------------------- | -- | ------- |
| HC                                                                               | `herb_common`             | Обычная трава / Common herb / Hierba común                                       | Herbalism 1    | Bulk `herb_base`       | 3  | A,C,L,E |
| HM                                                                               | `herb_magic`              | Магическая трава / Magic herb / Hierba mágica                                    | Herbalism 8    | Bulk `herb_base`       | 12 | A,L,E   |
| SH                                                                               | `shore_herbs`             | Береговые травы / Coastal herbs / Hierbas costeras                               | Herbalism 1    | Bulk `herb_base`       | 4  | C,E     |
| MH                                                                               | `marsh_herb`              | Болотная трава / Marsh herb / Hierba del pantano                                 | Herbalism 6    | Bulk `herb_base`       | 4  | A,C,L   |
| DP                                                                               | `desert_plant`            | Пустынное растение / Desert plant / Planta del desierto                          | Herbalism 12   | Bulk `herb_base`       | 4  | A,C,E   |
| TH                                                                               | `toxic_herb`              | Ядовитая трава / Toxic herb / Hierba tóxica                                      | Herbalism 18   | Bulk `herb_base`       | 4  | A,L,E   |
| FM                                                                               | `forest_mushroom`         | Лесной гриб / Forest mushroom / Seta del bosque                                  | Herbalism 1    | Bulk `herb_base`       | 4  | C       |
| RB                                                                               | `reed_bundle`             | Пучок камыша / Reed bundle / Manojo de juncos                                    | Herbalism 1    | Bulk `fiber`           | 4  | L,E     |
| WC                                                                               | `wood_common`             | Обычная древесина / Common wood / Madera común                                   | Woodcutting 1  | Bulk `wood`            | 3  | M,B,E   |
| WD                                                                               | `wood_dark`               | Тёмная древесина / Dark wood / Madera oscura                                     | Woodcutting 6  | Bulk `wood`            | 10 | M,E     |
| FP                                                                               | `frostpine_wood` **new**  | Морозная сосна / Frostpine wood / Madera de pino gélido                          | Woodcutting 12 | Bulk `wood`            | 6  | M,B,E   |
| AB                                                                               | `ancient_bark`            | Древняя кора / Ancient bark / Corteza antigua                                    | Woodcutting 18 | Bulk `wood`            | 30 | M,B,E   |
| IO                                                                               | `iron_ore`                | Железная руда / Iron ore / Mineral de hierro                                     | Mining 1       | Bulk `ore`             | 6  | H,B     |
| CO                                                                               | `coal`                    | Уголь / Coal / Carbón                                                            | Mining 1       | Bulk `fuel`            | 4  | H,B     |
| ST                                                                               | `stone_chunk`             | Кусок камня / Stone chunk / Trozo de piedra                                      | Mining 1       | Bulk `stone`           | 4  | H,B,E   |
| SA                                                                               | `salt_crystal`            | Кристалл соли / Salt crystal / Cristal de sal                                    | Mining 6       | Bulk `seasoning`       | 4  | C       |
| GE                                                                               | `gem_common`              | Обычный самоцвет / Common gem / Gema común                                       | Mining 12      | Bulk `gem`             | 35 | H,E     |
| SO                                                                               | `sunscar_ore` **new**     | Руда Санскара / Sunscar ore / Mineral de Sunscar                                 | Mining 18      | Bulk `ore`             | 8  | H,B     |
| SF                                                                               | `shore_fish`              | Прибрежная рыба / Coastal fish / Pez costero                                     | Fishing 1      | Bulk `fish`            | 4  | C       |
| MF                                                                               | `marsh_fish`              | Болотная рыба / Marsh fish / Pez del pantano                                     | Fishing 6      | Bulk `fish`            | 4  | C       |
| OF                                                                               | `oasis_fish`              | Оазисная рыба / Oasis fish / Pez del oasis                                       | Fishing 12     | Bulk `fish`            | 4  | C       |
| DF                                                                               | `deep_marsh_fish` **new** | Глубинная болотная рыба / Deep-marsh fish / Pez de las profundidades del pantano | Fishing 18     | Bulk `fish`            | 8  | C       |
| BM                                                                               | `boar_meat`               | Мясо кабана / Boar meat / Carne de jabalí                                        | Hunting 1      | Bulk `meat`            | 5  | C       |
| WP                                                                               | `wolf_pelt`               | Волчья шкура / Wolf pelt / Piel de lobo                                          | Hunting 1      | Bulk `hide`            | 8  | M,B,E   |
| WF                                                                               | `wolf_fang`               | Волчий клык / Wolf fang / Colmillo de lobo                                       | Hunting 2      | Special `trophy`       | 12 | M,B     |
| SS                                                                               | `spider_silk`             | Паучий шёлк / Spider silk / Seda de araña                                        | Hunting 6      | Bulk `fiber`           | 18 | M,L,E   |
| BH                                                                               | `bear_hide` **new**       | Медвежья шкура / Bear hide / Piel de oso                                         | Hunting 12     | Bulk `hide`            | 12 | M,B     |
| TS                                                                               | `troll_sinew` **new**     | Сухожилие тролля / Troll sinew / Tendón de trol                                  | Hunting 18     | Special `monster_part` | 18 | H,M,B,E |

The table is authoritative for future profession access. In particular:

- Iron and coal move to mining level 1 to create a usable entry path.
- Salt explicitly belongs to mining.
- Silk harvesting requires hunting 6.
- Existing inventory does not become unusable when a gathering requirement changes.
- Resource gates are explicit profession levels, without the current zone-band multiplier.
- Existing character levels, travel rules, and region levels are unchanged.

Location abbreviations below are exact expansions:

```
Wn = westwild_n...
Fn = frostspine_n...
An = ashen_n...
Sn = sunscar_n...
Mn = mireveil_n...
Coast = south_coast_shore
Mine = old_mine_entrance
```

Environmental gathering delivers **one unit**, using the listed unconditional chance within the selected profession’s roll.

| MaterialComplete environmental sources and probabilities |                                                                                                    |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| HC                                                       | W1 .55; W2 .45; W3/W4/W5 .35 each; W8 .25; A3c1 .30                                                |
| HM                                                       | W9 .10; W10 .15; A3c1 .35                                                                          |
| SH                                                       | Coast .20                                                                                          |
| MH                                                       | M1 .50; M2 .45; M4 .25; M6 .35; M7 .30; M8 .25                                                     |
| DP                                                       | S5a1 .35; S6 .30                                                                                   |
| TH                                                       | M8a2 .45; M9 .25; M10 .50                                                                          |
| FM                                                       | W4 .25; W6 .30; W7 .35; W9 .40; W10 .45; W11 .50                                                   |
| RB                                                       | M3 .55; M5 .30; M7 .40                                                                             |
| WC                                                       | W2 .15; W3 .25; W4 .35; W5 .40                                                                     |
| WD                                                       | W6 .45; W7 .50; W8 .25; W11 .35                                                                    |
| FP                                                       | **Add:** F4 .45; F6 .55                                                                            |
| AB                                                       | **Add:** W11 .20; A3c1 .30                                                                         |
| IO                                                       | Mine .65                                                                                           |
| CO                                                       | Mine .30                                                                                           |
| ST                                                       | W8 .30; S2 .30; S3 .35; S4 .45; S5 .40; S8 .45; S8a2 .50; S9 .30; S10 .35; S11 .30; **add F6 .40** |
| SA                                                       | S7 .55; S9 .30; S10 .45                                                                            |
| GE                                                       | **Add:** Mine .05; F6 .35                                                                          |
| SO                                                       | **Add:** S10 .20; S11 .30                                                                          |
| SF                                                       | Coast .70                                                                                          |
| MF                                                       | M4 .45; M5 .40; M5a1 .60; M8 .45                                                                   |
| OF                                                       | S5a1 .65                                                                                           |
| DF                                                       | **Add:** M8 .20; M10 .45                                                                           |

Preserve existing row order and append new rows in the order shown. At new F6 mining sources, stone precedes gem.

Probabilities are **not renormalized** around locked resources. A roll selecting a locked resource returns localized access feedback and delivers nothing. Remaining probability is an empty result. Validate that each location/profession sum is at most 1.

Hunting sources:

| MaterialEligible placed mobs and locationsHarvest |                                                                   |                                |
| ------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------ |
| BM                                                | `forest_boar`: W2, W3, W5, W7                                     | One selected unit, guaranteed  |
| WP, WF                                            | `forest_wolf`: W3, W4, W6, W7; `white_wolf`: F2–F6                | Choose pelt or fang; one total |
| SS                                                | `forest_spider`: W4, W5, W7; `swamp_spider`: M3, M4               | One, guaranteed                |
| BH                                                | `bear`: W6–W11                                                    | One, guaranteed                |
| TS                                                | `troll`: F7, F8, F10; `ice_troll`: F8–F10; `troll_chief`: F9, F10 | One, guaranteed                |

Harvest quantity does not increase with pack size or elite status.

Existing ordinary loot remains supplementary: boar meat `.75`, forest-wolf pelt `.60`, fang `.25`, and forest-spider silk `.50`, through their existing combat reward policies. These drops have no profession gate and grant no profession XP.

No other combat drop tables are changed. New hides and sinew are harvest-only.

For filtering and compatibility:

- Environmental and harvest actions validate an explicit manifest entry before delivery.
- Do not widen normal-combat reward-family allowlists.
- Do not rely on filtered reagents or unplaced legacy creatures.
- `spider_venom`, `bat_wing`, `stone_core`, `treant_heart`, `golem_fragment`, and other unused legacy materials remain compatibility content, not required V1 inputs.
- `ancient_bark` gains real gathering sources without depending on the unplaced treant.
- Preserve existing non-V1 gathering entries, inventory, and sale behavior.
- Reverse-index recipe consumers from the frozen recipe catalog; do not maintain a second handwritten list of uses.

**E. Complete recipe matrix**

These defaults apply to **every recipe**:

- Output quantity: **one**.
- Crafting gold fee: **zero**.
- Learning and execution location: any of the six guilds.
- Starter recipes: guaranteed under the ownership rules in G.
- Other recipes: learn at their required profession level.
- Learning cost: L6 **25 gold**, L12 **75 gold**, L18 **150 gold**.
- New recipe unless explicitly marked existing.
- No recipe output is an input to another recipe.

Equipment band policy:

| Recipe levelTierRaritySecondary rolls |    |          |                                   |
| ------------------------------------- | -- | -------- | --------------------------------- |
| 1                                     | 1  | common   | None                              |
| 6                                     | 5  | common   | None                              |
| 12                                    | 5  | uncommon | Exactly one ordinary allowed roll |
| 18                                    | 10 | uncommon | Exactly one ordinary allowed roll |

The weapon table below is a closed expansion into **30 recipes**. For each family and each listed level:

```
recipe_id = pe_<family>_<two-digit-level>
output_item_id = field_<family>
```

For example, the first row defines `pe_sword_1h_01`, `pe_sword_1h_12`, and `pe_sword_1h_18`. There are no additional generated combinations.

| Canonical familyProfessionL1 inputsL12 inputsL18 inputs |   |             |                 |                     |
| ------------------------------------------------------- | - | ----------- | --------------- | ------------------- |
| `sword_1h`                                              | B | IO3 CO1 WC1 | IO4 CO2 FP2 WF1 | SO3 IO3 CO3 AB1 TS1 |
| `sword_2h`                                              | B | IO4 CO2 WC1 | IO6 CO3 FP2 WF1 | SO5 IO4 CO4 AB1 TS1 |
| `axe_2h`                                                | B | IO4 CO2 WC1 | IO6 CO3 FP2 WF1 | SO5 IO4 CO4 AB1 TS1 |
| `daggers`                                               | B | IO3 CO1 WP1 | IO4 CO2 BH1 WF1 | SO3 IO2 CO2 BH1 TS1 |
| `bow`                                                   | E | WC4 RB2     | FP4 SS2 GE1     | AB3 FP2 SS3 TS1     |
| `magic_staff`                                           | E | WC3 RB1 HC2 | FP3 SS1 GE1 HM1 | AB2 GE2 SS2 HM2     |
| `wand`                                                  | E | WC2 RB1 HC2 | FP2 SS1 GE1 HM1 | AB1 GE2 SS2 HM2     |
| `holy_staff`                                            | E | WC3 RB1 SH2 | FP3 SS1 GE1 SH2 | AB2 GE2 SS2 DP2     |
| `holy_rod`                                              | E | WC2 RB1 SH2 | FP2 SS1 GE1 SH2 | AB1 GE2 SS2 DP2     |
| `tome`                                                  | E | RB4 WP1 HC2 | RB4 SS2 GE1 HM1 | RB6 SS3 GE2 AB1     |

Weapon purposes are fixed:

- L1: chosen basic family, competing with a 45-gold basic vendor purchase.
- L12: chosen family at T5 uncommon.
- L18: chosen family at T10 uncommon.
- NPC sale remains the existing field-template price, **5 gold**, regardless of crafted tier or rarity.

Regional identity follows the inputs: entry Westwild/Coast/Mine; advanced Frostspine plus Westwild/Mireveil; late projects add Sunscar, ancient woodland/Ashen garden, and relevant hunting materials.

Nine offhand recipes:

| Recipe IDProfession / levelInputsOutput |     |                 |                |
| --------------------------------------- | --- | --------------- | -------------- |
| `pe_shield_06`                          | B6  | IO4 CO2 ST2 WF1 | `field_shield` |
| `pe_shield_12`                          | B12 | IO5 CO2 FP2 BH1 | `field_shield` |
| `pe_shield_18`                          | B18 | SO4 IO3 CO3 TS1 | `field_shield` |
| `pe_focus_06`                           | E6  | WD2 ST2 RB2     | `field_focus`  |
| `pe_focus_12`                           | E12 | FP2 GE1 SS2 HM1 | `field_focus`  |
| `pe_focus_18`                           | E18 | AB2 GE2 SS2 TH1 | `field_focus`  |
| `pe_censer_06`                          | E6  | WD2 ST2 SH2     | `field_censer` |
| `pe_censer_12`                          | E12 | FP2 GE1 SS2 DP1 | `field_censer` |
| `pe_censer_18`                          | E18 | AB2 GE2 SS2 DP2 | `field_censer` |

All offhands use the equipment band policy and sell for 5. L6 is the first crafted offhand milestone; L12 and L18 improve predictable quality/tier. Existing offhand compatibility rules remain authoritative.

Twelve armor recipes:

| Recipe IDProfession / levelInputsOutputStatus |     |                 |                       |                     |
| --------------------------------------------- | --- | --------------- | --------------------- | ------------------- |
| `pe_heavy_chest_01`                           | H1  | IO4 CO2         | `field_heavy_chest`   | New                 |
| `pe_heavy_helmet_06`                          | H6  | IO3 CO2 ST2     | `field_heavy_helmet`  | New                 |
| `pe_heavy_legs_12`                            | H12 | IO6 CO3 GE1     | `field_heavy_legs`    | New                 |
| `pe_heavy_chest_18`                           | H18 | SO6 IO4 CO4 TS2 | `field_heavy_chest`   | New                 |
| `trail_vest`                                  | M1  | WP2 WC2         | `trail_vest`          | Existing, preserved |
| `pe_medium_helmet_06`                         | M6  | WP2 WD1 WF1     | `field_medium_helmet` | New                 |
| `pe_medium_legs_12`                           | M12 | BH3 SS2 FP1     | `field_medium_legs`   | New                 |
| `pe_medium_chest_18`                          | M18 | BH4 SS3 AB1 TS1 | `field_medium_chest`  | New                 |
| `pe_light_chest_01`                           | L1  | RB4 HC2         | `field_light_chest`   | New                 |
| `pe_light_helmet_06`                          | L6  | RB3 SS1 MH1     | `field_light_helmet`  | New                 |
| `pe_light_legs_12`                            | L12 | SS3 RB3 HM2     | `field_light_legs`    | New                 |
| `pe_light_chest_18`                           | L18 | SS4 RB4 HM2 TH2 | `field_light_chest`   | New                 |

Armor uses the equipment band policy. `trail_vest` retains its template and sale price of **12**; all other outputs sell for **5**.

Chest → helmet → legs → improved chest is the complete V1 slot ladder. Boots and gloves remain available through existing vendors and loot; no extra craft recipes are added.

Six alchemy recipes:

| Recipe IDLevelInputsOutputRecoverySellStatus |    |             |                          |       |    |                           |
| -------------------------------------------- | -- | ----------- | ------------------------ | ----- | -- | ------------------------- |
| `field_tonic`                                | 1  | HC3         | `health_potion_small`    | HP30  | 5  | Existing                  |
| `field_mana`                                 | 2  | HC5         | `mana_potion`            | MP50  | 12 | Existing                  |
| `pe_alchemy_health_06`                       | 6  | HC3 MH2     | `health_potion`          | HP80  | 15 | New recipe, existing item |
| `pe_alchemy_mana_12`                         | 12 | HM2 DP2     | `pe_mana_potion_medium`  | MP100 | 12 | New                       |
| `pe_alchemy_health_18`                       | 18 | HC4 TH2 DP1 | `pe_health_potion_large` | HP150 | 15 | New                       |
| `pe_alchemy_mana_18`                         | 18 | HM3 TH2 DP2 | `pe_mana_potion_large`   | MP160 | 18 | New                       |

Six cooking recipes:

| Recipe IDLevelInputsOutputRecoverySellStatus |    |                 |                      |             |    |          |
| -------------------------------------------- | -- | --------------- | -------------------- | ----------- | -- | -------- |
| `trail_ration`                               | 1  | BM1 HC1         | `field_ration`       | HP40        | 5  | Existing |
| `pe_cooking_shore_01`                        | 1  | SF1 SH1         | `pe_shore_broth`     | HP25, MP15  | 4  | New      |
| `pe_cooking_marsh_06`                        | 6  | MF2 MH1 SA1     | `pe_marsh_stew`      | HP80, MP20  | 6  | New      |
| `pe_cooking_boar_12`                         | 12 | BM3 FM2 SA1     | `pe_boar_feast`      | HP120       | 8  | New      |
| `pe_cooking_oasis_12`                        | 12 | OF2 DP1 SA1     | `pe_oasis_meal`      | HP100, MP50 | 8  | New      |
| `pe_cooking_deep_18`                         | 18 | DF2 BM2 FM2 SA1 | `pe_deep_marsh_meal` | HP180, MP80 | 12 | New      |

Consumables have common rarity, no item tier or secondary rolls, and use the existing `heal`/`mana` fields. New consumables have weight 1, requirements level 1/attributes 0, `buy_price=0`, no vendor offer, and otherwise zero equipment statistics.

Cooking outputs additionally have `consumable_family='food'`. They use existing inventory and battle consumption, including existing caps and turn costs. No persistent food effects are introduced.

Exact identities of new outputs:

| Itemru / en / es         |                                                                              |
| ------------------------ | ---------------------------------------------------------------------------- |
| `pe_mana_potion_medium`  | Среднее зелье маны / Medium mana potion / Poción de maná mediana             |
| `pe_health_potion_large` | Большое зелье здоровья / Large health potion / Poción de salud grande        |
| `pe_mana_potion_large`   | Большое зелье маны / Large mana potion / Poción de maná grande               |
| `pe_shore_broth`         | Прибрежная уха / Coastal fish broth / Caldo de pescado costero               |
| `pe_marsh_stew`          | Болотная похлёбка / Marsh stew / Guiso del pantano                           |
| `pe_boar_feast`          | Жаркое из кабана / Boar roast / Asado de jabalí                              |
| `pe_oasis_meal`          | Оазисное рыбное блюдо / Oasis fish meal / Plato de pescado del oasis         |
| `pe_deep_marsh_meal`     | Сытная болотная трапеза / Hearty marsh meal / Comida sustanciosa del pantano |

Disposition of the four inactive recipes:

| Historical IDFrozen disposition |                                                                                               |
| ------------------------------- | --------------------------------------------------------------------------------------------- |
| `alchemy_minor_health_potion`   | Inactive compatibility definition; superseded by `field_tonic`                                |
| `cooking_field_ration`          | Inactive compatibility definition; superseded by `trail_ration`; never grant a potion as food |
| `blacksmith_iron_sword`         | Inactive compatibility definition; superseded by `pe_sword_1h_01`                             |
| `arcane_focus_orb`              | Inactive compatibility definition; superseded by `pe_focus_06`                                |

Inactive definitions are not learnable, not counted among 63, and not executable through a direct runtime call. Their existing output items and owned instances remain valid.

**F. Craft output/gear policy**

Extend recipe definitions with explicit:

```
catalog_version = 1
active
starter
learning_gold
training_ceiling
output_spec:
    kind: gear | consumable
    item_id
    quantity
    item_tier: integer | null
    rarity
    secondary_policy: none | ordinary_one | not_applicable
```

The runtime must:

1. Read the recipe from the server catalog.
2. Validate ownership, persisted profession level, guild, and inputs.
3. Generate allowed secondaries using the existing PR230 helper.
4. Call `grant_item_to_player` with an explicit `gear_spec` for every equipment output.
5. Require exact delivery before committing.

Equipment specification:

```
base_item_id = recipe output
item_tier = recipe tier
rarity = recipe rarity
secondary_rolls = [] or one ordinary generated roll
enhance_level = 0
durability = 100
max_durability = 100
```

Use `source='crafting'`, the caller’s transaction, and provenance:

```
{
  "source": "crafting",
  "catalog_version": 1,
  "recipe_id": "...",
  "profession_key": "...",
  "crafter_player_id": 123,
  "location_id": "...",
  "craft_request_id": "..."
}
```

Leave `source_settlement_id` null; a crafting receipt is not a combat settlement.

Do not pass an open-world combat source policy to a guild craft. Explicit recipe validation authorizes the output.

Instance IDs, exact rolls, tier, rarity, and delivery are recorded in the result receipt. A retry returns those values without rerolling.

Existing templates continue to determine family, slot, requirements, comparison, equip behavior, enhancement, and advancement. No crafted stat bonus, special affix pool, rarity upgrade, or alternate inventory is added.

All previously owned gear—including high-rarity crafted gear—is grandfathered unchanged.

**G. Recipe ownership model**

Create:

```
CREATE TABLE player_recipe_knowledge (
    player_id INTEGER NOT NULL REFERENCES players(telegram_id),
    recipe_id TEXT NOT NULL,
    acquired_via TEXT NOT NULL
        CHECK (acquired_via IN ('grandfather', 'starter', 'guild')),
    learned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    learned_location_id TEXT,
    gold_paid INTEGER NOT NULL DEFAULT 0 CHECK (gold_paid >= 0),
    catalog_version INTEGER NOT NULL CHECK (catalog_version >= 1),
    PRIMARY KEY (player_id, recipe_id)
);
```

There is no foreign key to a runtime recipe table; recipes remain a static catalog.

Bootstrap is deliberately different for existing and new players:

- **Existing players:** migration grants exactly `field_tonic`, `field_mana`, `trail_ration`, and `trail_vest`, with `acquired_via='grandfather'`.
- **New registrations after migration:** grant all 17 starter recipes with `acquired_via='starter'`.
- **Existing players’ 13 newly introduced starter recipes:** guaranteed free learning at any guild, with `acquired_via='guild'`, gold paid 0. Do not fabricate historical ownership.
- The known `field_mana` recipe still requires alchemy 2 to craft.
- No later recipe is automatically granted by migration or by reaching a level.

Learning uses one confirmed server-issued action and one transaction. It checks active catalog membership, guild presence, persisted profession level, current gold, and existing knowledge.

For a fresh valid action requesting an already-known recipe: return `already_known`, charge zero, and retain the original acquisition row. A replay of a successful learning action returns its original receipt.

Knowledge never expires and survives restart. Learning awards no XP.

**H. Persistence/migration specification**

Create a named migration ledger:

```
CREATE TABLE economy_schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

The migration marker is exactly:

```
professions_economy_v1
```

Run the migration inside a startup-owned `BEGIN IMMEDIATE` transaction, before gameplay handlers can execute. Helpers must use the supplied connection and must not commit internally or use an `executescript` operation that silently changes the transaction boundary.

Migration order:

1. Inspect the existing crafting table, indexes, triggers, and referencing tables.
2. Accept the frozen-baseline schema or the already-migrated schema. An unexpected incompatible schema stops startup with a diagnostic; do not guess or discard rows.
3. Create `player_crafting_professions_pev1_new` with the same columns, primary key, foreign key, level/XP checks, and the seven-key constraint:

```
CHECK (profession_key IN (
    'heavy_armor', 'medium_armor', 'light_armor',
    'blacksmith', 'arcane_engineer', 'alchemy', 'cooking'
))
```

4. Copy `player_id`, `profession_key`, `level`, and `exp` exactly.
5. Validate row counts and bidirectional row equality before replacing the table.
6. Drop the old table and rename the replacement within the same transaction. Keep foreign-key enforcement enabled. The inspected baseline has no dependent child table requiring a parallel migration.
7. Insert missing crafting rows at level 1/XP0 for all seven keys. Existing three rows must not be overwritten.
8. Ensure missing gathering identities exist at level 1/XP0; never overwrite existing rows.
9. Create knowledge and result-receipt tables.
10. Grant only the four grandfathered recipes to existing players.
11. Run foreign-key validation and preservation assertions.
12. Insert the migration marker last, then commit.

Any exception rolls back the complete migration, including DDL, knowledge, defaults, and marker. Do not attempt partial repair.

On repeated startup:

- Verify the expected schema.
- Skip the rebuild and grandfather backfill when the marker exists.
- Normal player-initialization helpers remain idempotent.
- Do not infer “new player” from an empty knowledge ledger.

Migration must not rewrite:

- Gathering levels/XP.
- Existing crafting levels/XP.
- Inventory rows or quantities.
- Gear IDs or any gear field.
- Chapter objectives/history.
- Harvest claims.
- Prepared/applied combat settlement JSON or status.
- Build/mastery/progression data.

Item seeding runs successfully before the bot accepts actions. Use insert/update operations, never `INSERT OR REPLACE` on referenced item rows. Reconcile only the V1 whitelist’s sale-price fields where necessary; do not blanket-update equipment templates.

**I. Economy/pricing invariants**

All recipe inputs have a nonzero raw sale value. All output sale values are fixed in E.

For every recipe:

\\[ \text{output NPC sale value} < \sum(\text{input quantity}\times\text{input NPC sale price}) \\]

Representative fixed comparisons:

| ProductionRaw sale opportunity costOutput sale |    |    |
| ---------------------------------------------- | -- | -- |
| Small HP tonic                                 | 9  | 5  |
| Mana potion                                    | 15 | 12 |
| Trail ration                                   | 8  | 5  |
| Trail vest                                     | 22 | 12 |
| Basic one-handed sword                         | 25 | 5  |
| Basic heavy chest                              | 32 | 5  |
| HP80 potion                                    | 17 | 15 |
| Coastal broth                                  | 8  | 4  |
| Deep-marsh meal                                | 38 | 12 |

Paid learning costs exceed the resale of any single resulting output. All 46 paid recipes together cost **4,475 gold**; learning everything is optional.

Self-supply can beat an equivalent basic purchase:

- HP30: raw materials worth 9 versus vendor price 30.
- MP50: raw materials worth 15 versus vendor price 60.
- Basic one-handed sword: raw materials worth 25 versus vendor price 45.
- Basic heavy chest: raw materials worth 32 versus vendor price 60.

These are opportunity-cost comparisons, not claims that gathering is free or that crafting is the fastest acquisition method.

Preserve:

- Existing vendor offers and purchase prices.
- Field-equipment sale prices.
- Enhancement prices/chances.
- Advancement prices/materials.
- Crystal exchange: 10 shards + 25 gold → one crystal.
- Inn price: 12 gold.
- Death policy.
- Ordinary combat gold and material loot.

Extend existing stack selling to the **12 V1 consumable output IDs**, using their table prices. Retain material selling and existing gear selling. Sell exactly one unit per confirmed action; do not add bulk selling.

No new raw-material vendor offers exist. `buy_price=0` means unavailable for purchase, never a free item.

The conversion graph contains no crafted-output input cycle. Existing shard exchange also loses raw resale value: inputs worth 175 gold produce a crystal selling for 40.

Unlimited repeated gathering remains an intentional source of items and gold through player actions. The contract does not promise a bounded gold-per-hour rate. No cooldown is required to satisfy the conservation invariants above; throughput tuning is deferred.

**J. Hunting specification**

Harvest authorization must use the saved applied settlement, not the encounter’s victory flag alone.

A valid claim requires all of:

1. Caller is `pve_encounters.owner_player_id`.
2. Encounter status is `victory`.
3. Corresponding settlement status is `applied`.
4. Settlement schema is supported and policy is one of the existing supported `legacy_v0` or `field_loot_v1` policies.
5. Plan identity, owner, and canonical location match the encounter.
6. Owner appears in `eligible_recipient_ids`.
7. Owner does not appear in `defeated_participant_ids`.
8. The applied result contains that owner as a reward recipient.
9. The selected enemy unit appears in the plan’s saved `enemy_units`.
10. That unit’s mob/item pair is present in D’s harvest manifest.
11. Owner is currently peaceful and at the encounter’s canonical location.
12. `0 <= now - finished_at <= 1,800 seconds`.
13. Required hunting level is satisfied.
14. No existing `(encounter_id, player_id)` harvest claim exists.

Unknown versions, missing authority, `prepared`, and `legacy_review` settlements fail closed. Do not recover or reinterpret combat rewards inside harvesting.

The UI exposes distinct harvest choices from the saved roster. For duplicate eligible units yielding the same item, choose the first unit by stable `unit_id` ordering; do not multiply output.

The confirmation token binds encounter, unit, mob, and item. One encounter permits one owner choice total, including mixed encounters.

Retain `pve_harvest_claims` and its primary key. Claim insertion, one-item delivery, hunting XP, chapter objective, action consumption, and result receipt commit together.

Existing claims are retained. A surviving party winning after the owner was defeated never creates owner harvest entitlement. Foreign claims, repeat claims, wrong-location claims, and expired claims deliver nothing.

**K. Transaction/receipt model**

Create:

```
CREATE TABLE economy_action_receipts (
    player_id INTEGER NOT NULL REFERENCES players(telegram_id),
    request_id TEXT NOT NULL,
    action_kind TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    catalog_version INTEGER NOT NULL CHECK (catalog_version >= 1),
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (player_id, request_id)
);

CREATE INDEX idx_economy_receipts_player_time
ON economy_action_receipts(player_id, created_at, request_id);
```

Purpose: retain the committed economic result so retries and lost Telegram responses cannot repeat charges, output generation, XP, or objectives.

Receipt JSON uses language-neutral IDs and numbers:

```
schema_version, action_kind, status, player_id, location_id
recipe_id or null
consumed: [{item_id, quantity}]
granted: [{item_id, quantity, instance_ids, gear_specs}]
gold_delta, gold_after
progression: [{
    profession_key, old_level, old_exp,
    new_level, new_exp, xp_awarded
}]
source: action-specific authority
details: missing inputs, recovery amounts, recipient ID, or rejection reason
```

No localized prose is authoritative. Render receipts in the player’s current language.

Action keys:

- UI-confirmed mutations: `ui:<server_token>`.
- Gathering: preserve existing `gather:<chat_id>:<message_id>` identity.
- Never use client-supplied recipe/material quantities as authority.
- Hash the canonical server intent using SHA-256; bind action kind, actor, catalog version, and intended parameters.

Retain the existing action-token table and 900-second expiry. Token payloads for new flows are versioned server JSON. Existing incompatible previews must refresh instead of executing through an old path.

Transaction sequence:

1. `BEGIN IMMEDIATE`.
2. Look up the owner’s receipt for this request.
3. If found and matching the requested action, return the recorded result without mutation—even if location, expiry, or current state has since changed.
4. Otherwise validate the token/request and current authoritative state.
5. Perform all debits, grants, XP, objectives, and claim/knowledge updates.
6. Mark the token used and insert the receipt.
7. Commit.
8. Perform Telegram I/O after commit.

A valid consumed intent that encounters a business rejection, such as insufficient materials, records that result with no economic mutation. A new attempt requires a fresh preview.

Invalid/foreign/stale tokens do not authorize receipt creation. Unexpected exceptions roll back the token, mutations, and receipt together.

Specific boundaries:

| ActionAtomic contents        |                                                                                            |
| ---------------------------- | ------------------------------------------------------------------------------------------ |
| Learn                        | Token, gold debit, knowledge insertion, receipt                                            |
| Craft                        | Token, aggregated input consumption, exact output delivery, XP, chapter objective, receipt |
| Gather                       | Stable request, one roll, delivery or empty/locked result, XP, chapter objective, receipt  |
| Harvest                      | Token, eligibility, unique claim, delivery, XP, chapter objective, receipt                 |
| Stack sale                   | Token, exact expected stack quantity, decrement, gold credit, objective, receipt           |
| Crystal exchange             | Token, chapter eligibility, shard/gold debit, crystal delivery, receipt                    |
| Inn                          | Token, locked eligibility/resources, one payment, restoration, receipt                     |
| Direct gift                  | Token, locked sender/recipient and item state, one-unit transfer, receipt                  |
| Out-of-battle consumable use | Existing token validation, consumption/recovery, receipt                                   |

Preserve existing gear mutation and battle-consumable receipts; do not replace combat or gear settlement systems.

For pre-migration gathering requests already present in `player_action_receipts` but lacking a result receipt: return a localized “already processed; historical details unavailable” response. Never reroll them. Continue checking this legacy ledger.

Keep V1 receipts durable without pruning. The journal exposes receipt history, five per page. A lost Telegram response is recovered by replaying the same action or opening history; recovery never silently repeats an action.

Narrow inn correction is **required**: move all state, service, peacefulness, funds, and “rest needed” checks under the write lock; bind a token; debit once; use existing effective-stat caps. Do not change the 12-gold price or create a new recovery mechanic.

Narrow direct-gift correction is **required**:

- Username entry resolves a registered recipient and opens a confirmation; it does not transfer.
- Freeze recipient player ID in the token.
- Re-read sender, recipient, ownership, quantity, and equipment state under the same transaction.
- Sender must be peaceful; recipient may receive a gift while busy because receiving does not alter their equipped state.
- Preserve one-unit gifting, self-gift rejection, and current public restrictions.
- Stack merging requires identical item ID, enhancement, and durability.
- Preserve those fields when creating the recipient row.
- Guarded sender debit must affect exactly one row.
- Legacy inventory equipment must be unequipped.
- Keep the existing public block on `gear_instance` gifting; do not activate the currently unreachable gear-transfer branch.
- Do not add trading, acceptance escrow, gold transfer, or recipient notifications.

**L. UX/navigation specification**

Add a **Professions** entry to `/journal`. Existing guild/workshop entry points route into the same navigation.

Flow:

```
Overview
→ Profession detail
→ Known / Learnable / Locked recipes
→ Recipe detail
→ Material detail / Sources
→ Craft or Learn preview
→ Confirm
→ Durable result
```

Overview shows all 12 professions, divided into gathering and crafting pages, six rows per page.

Profession detail shows:

- Level and XP/next threshold, or cap.
- Current unlocked milestone.
- Exact next unlock.
- Gathering resources or recipe lists.
- For crafting, the training ceiling of the current band.
- Clear “this recipe no longer grants XP” feedback.

Recipe filters:

- **Known:** owned active recipes.
- **Learnable:** unowned recipes whose profession requirement is met; insufficient gold is displayed, not hidden.
- **Locked:** future level requirements.
- A separate `craftable now` indicator requires knowledge, level, materials, peacefulness, and guild access.

Recipe detail shows quantity, full ingredients/owned/missing amounts, learning cost/source, equipment tier/rarity, recovery effect, sale value, XP and training ceiling. Secondary text says one ordinary roll where applicable; it does not promise a specific stat.

Material detail shows localized description, gathering/harvesting level, sources and chances, sale price, and paginated recipe consumers. Include hunting sources in the handbook.

Pagination:

- Profession overview, recipe lists, resources, source locations, and material consumers: **6 rows**.
- Existing inventory and stack-sale lists: **8 rows**, with no 20-item truncation.
- Harvest encounter lists and receipt history: **5 rows**.
- Sort recipes by required level then recipe ID; materials by required level then item ID.
- Clamp invalid pages and preserve a return route.
- Harvest queries must paginate after applying ownership/location/authority eligibility, not fetch 20 rows and then discard most of them.

Callbacks:

- New prefix: `pe_`.
- Read navigation: `pe_o`, `pe_p:<key>`, `pe_l:<key>:<filter>:<page>`, `pe_r:<recipe_id>`, `pe_m:<item_id>`, with bounded pagination suffixes.
- Mutation confirmation: `pe_a:<16-hex-token>`.
- Receipt opening uses a short server-issued lookup token, not a full serialized result.
- Enforce Telegram’s 64-byte callback limit.
- Keep message bodies at most 3,600 characters, splitting lists by pagination before rendering.
- Escape dynamic HTML.
- Old workshop/harvest/sale/inn callbacks open a current preview; they must not bypass the new authority.

Gathering keeps the current repeated reply-keyboard interaction. Each new Telegram message is a new action; a duplicated message is not. Validate the handler’s expected location/travel revision again under the transaction lock.

“Craft again” issues a new preview/token. It must not reuse the prior action token.

**M. Localization specification**

Full `ru`, `en`, and `es` coverage is mandatory for:

- Twelve profession names and descriptions.
- All resource and new consumable names/descriptions.
- Recipe names and band descriptors.
- Known, learnable, locked, craftable, and trivial-XP states.
- XP, cap, next milestone, and training-ceiling explanations.
- Learning costs and permanent ownership.
- Full ingredient/missing-material messages.
- Gathering probabilities and denied-access feedback.
- Harvest choices and all eligibility errors.
- Guild/source/location guidance.
- Preview and confirmation text.
- Success, rejection, duplicate, and recovered receipts.
- Sale, inn, and gift confirmations.
- Pagination and return navigation.
- Inactive historical recipe explanation.
- Historical receipt unavailable and unknown-content fallbacks.

Equipment recipe names are composed from the existing localized template name plus a localized band descriptor:

| Levelruenes |                      |                    |                           |
| ----------- | -------------------- | ------------------ | ------------------------- |
| 1           | Базовый образец      | Basic pattern      | Patrón básico             |
| 6           | Региональный образец | Regional pattern   | Patrón regional           |
| 12          | Продвинутый образец  | Advanced pattern   | Patrón avanzado           |
| 18          | Поздний альфа-проект | Late-alpha project | Proyecto avanzado de alfa |

Descriptions must state actual recovery amounts or gear output policy. Do not inherit Russian-only material descriptions into English/Spanish flows.

Known V1 content must have complete translations; missing-key tests must fail. Unknown historical content receives a localized neutral fallback while retaining its ID for diagnostics. Translation fallback must never make an inactive recipe executable.

**N. Exact file/module change map**

Paths below are repository-relative; no local checkout was created.

| FilesOwnership                                          |                                                                            |
| ------------------------------------------------------- | -------------------------------------------------------------------------- |
| `rpg/database.py`                                       | Startup transaction integration; all-profession/new-player bootstrap       |
| `rpg/game/alpha_schema.py`                              | Delegate profession schema ownership; preserve chapter/harvest tables      |
| **New** `rpg/game/profession_schema.py`                 | Named migration, seven-profession table, knowledge and receipt schemas     |
| `rpg/game/gathering_foundation.py`                      | Explicit resource identities/gates; remove zone multiplier for V1 manifest |
| `rpg/game/gathering_progression.py`                     | Frozen gather XP policy; preserve public compatibility wrappers            |
| **New** `rpg/game/profession_progression.py`            | Shared threshold/application policy and separate craft XP calculation      |
| **New** `rpg/game/profession_resources.py`              | Resource manifest, added source rows, harvest mapping, reverse consumers   |
| `rpg/game/locations.py`                                 | Apply exact new environmental source rows                                  |
| `rpg/game/items_data.py`                                | Five materials, eight consumables, explicit metadata                       |
| `rpg/game/seed.py`                                      | Idempotent item insertion and narrow V1 price reconciliation               |
| `rpg/game/crafting_foundation.py`                       | Explicit material groups and allowed profession/group additions            |
| **New** `rpg/game/profession_recipes.py`                | Exact 63-recipe catalog and inactive historical mapping                    |
| **New** `rpg/game/recipe_knowledge.py`                  | Bootstrap, query, and transactional learning                               |
| `rpg/game/crafting_runtime.py`                          | Persisted authority, explicit outputs, XP, atomic receipt                  |
| `rpg/game/gathering_runtime.py`                         | Durable outcomes and legacy request compatibility                          |
| `rpg/game/hunting.py`                                   | Applied-settlement eligibility and one-choice harvest                      |
| `rpg/game/action_receipts.py`                           | Versioned intent support and receipt lookup integration                    |
| **New** `rpg/game/economy_actions.py`                   | Simple receipt helpers; stack sale/exchange/inn/gift operations            |
| `rpg/game/resource_handbook.py`                         | All five professions, source/use pagination                                |
| **New** `rpg/handlers/professions.py`                   | Profession UI and `pe_` callbacks                                          |
| `rpg/handlers/chapter.py`                               | Journal/workshop routing, exchange/sale integration, chapter continuity    |
| `rpg/handlers/location.py`                              | Gathering feedback and inn preview/confirmation                            |
| `rpg/handlers/inventory.py`                             | Sale pagination, consumable sale/use receipts, narrow gift correction      |
| `rpg/game/contextual_keyboard.py`                       | Existing keyboard integration                                              |
| `rpg/bot.py`                                            | Register new handler; preserve existing routes                             |
| **New** `rpg/locales/professions.py`                    | Parallel ru/en/es profession-flow dictionaries                             |
| `rpg/locales/ru.py`, `en.py`, `es.py`                   | Include dictionaries and touched compatibility strings                     |
| `rpg/locales/items_ru.py`, `items_en.py`, `items_es.py` | Item names/descriptions                                                    |
| `rpg/game/i18n.py`                                      | Localized historical-content fallback only                                 |

Recipe validation retains existing allowed groups and adds only those needed by the manifest: `stone`, `seasoning`, and the necessary hide/fiber/herb/gem membership for listed consumers. Specials remain explicitly separated.

Do not modify combat balance, reward policy versions, ordinary loot tables, field templates, advancement, or enhancement. `gear_instances.py`, `field_catalog.py`, and `pve_reward_settlement.py` are integration authorities and should require no behavioral rewrite.

New test files:

```
rpg/tests/test_professions_economy_v1_catalog.py
rpg/tests/test_professions_economy_v1_progression.py
rpg/tests/test_professions_economy_v1_sources.py
rpg/tests/test_professions_economy_v1_migration.py
rpg/tests/test_professions_economy_v1_knowledge.py
rpg/tests/test_professions_economy_v1_transactions.py
rpg/tests/test_professions_economy_v1_hunting.py
rpg/tests/test_professions_economy_v1_economy.py
rpg/tests/test_professions_economy_v1_ui.py
rpg/tests/test_professions_economy_v1_journeys.py
```

Update affected existing profession, crafting, alpha-transaction, inn, and itemization tests for intentional contract changes. Do not weaken unrelated assertions.

**O. Internal implementation workstreams**

Use one branch and **one Draft PR**, with these internal commits/workstreams:

1. **Persistence:** named migration, bootstrap, knowledge/receipt schemas, preservation tests.
2. **Resource authority:** explicit gates, source additions, material identities, gather/hunting source coverage.
3. **Progression and ownership:** XP boundaries, permanent learning, exact starter compatibility.
4. **Recipe content and outputs:** 63 recipes, eight consumables, explicit gear specifications, validation.
5. **Economic transactions:** receipts, sale pagination, exchange recovery, inn/gift conservation.
6. **UX and localization:** complete navigation, source handbook, current-menu routing, all three languages.
7. **Acceptance and documentation:** production journeys, focused regressions, one final full suite, evidence, docs reconciliation.

These are commits within one coherent Epic, not separate PRs.

**P. Acceptance journey matrix**

Journey evidence must distinguish real production acquisitions from test-fixture setup.

Allowed controls in production journeys: deterministic RNG seeds, controlled clock, mocked Telegram transport, and selection among genuinely available encounters/actions.

Forbidden shortcuts: inserting materials/gold/knowledge/XP, raising profession or character levels directly, increasing player combat statistics beyond legal progression, bypassing rewards, or calling item grants as proof of acquisition.

Migration and adversarial unit tests may use fixtures; they must be labeled as such.

| JourneyRequired production behavior |                                                                                                                                                                                                                                                                     |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. New character                    | Register through the normal path; see 12 professions and 17 known starters; gather; gain XP; craft a starter; reach crafting 6; pay to learn a level-6 recipe; craft and use/equip its output                                                                       |
| 2. Mining / smith / heavy           | Mine iron/coal at Mine; stone and salt from real nodes; advance through gems at F6 and Sunscar ore; craft all heavy milestones and the smith weapon/shield milestones                                                                                               |
| 3. Wood / fiber / arcane            | Gather common/dark/frostpine/bark through real nodes; gather reeds; harvest silk; craft light armor and arcane milestones, including focus and censer                                                                                                               |
| 4. Herbalism / alchemy              | Progress common → marsh → desert → toxic sources; acquire magic herbs; craft all six alchemy recipes and consume HP/mana outputs                                                                                                                                    |
| 5. Fishing / cooking                | Progress Coast → Mireveil → Sunscar oasis → deep marsh; craft all six foods; verify both HP-only and mixed recovery                                                                                                                                                 |
| 6. Hunting                          | Win real owner encounters; harvest meat/pelt/fang/silk/hide/sinew; use them in recipes; verify one claim per mixed/pack encounter                                                                                                                                   |
| 7. Gear integration                 | Craft every canonical weapon family; compare/equip; obtain a normal vendor item and real combat loot; enhance and advance a crafted instance while preserving ID/rolls/provenance                                                                                   |
| 8. Migration/restart                | Start from frozen-baseline fixtures containing progressed professions, inventories, high-rarity crafted gear, chapter state, and prepared settlement; migrate twice/restart; compare preserved values and recover the prepared settlement through its existing path |
| 9. Learning authority               | Successful paid/free learning; duplicate callback; fresh duplicate-learning token; insufficient gold; missing level; wrong guild/location; expiry; travel away/back; restart; lost response                                                                         |
| 10. Conservation                    | Concurrent craft/sell/gift on the same resources; duplicate gather/harvest; delivery exception rollback; full/partial stacks; failed inn checks; duplicate exchange; vendor/craft/sale inequalities                                                                 |
| 11. Languages                       | Complete representative overview → source → learning → craft → result → recovery navigation in ru/en/es; include missing inputs, locked resource, and stale action                                                                                                  |

Across the production-journey corpus:

- Acquire **all 28 mandatory materials through their real delivering paths**.
- Successfully craft **all 63 recipes** using earned inputs.
- Demonstrate all 12 professions reaching level 20 through the frozen policies.
- Earn learning gold through normal registration, chapter/combat rewards, contracts, and legitimate sales.
- Preserve the existing Aster–Elmor chapter sequence and four live recipe objectives.
- Exercise defeated-owner party victory rejection separately from eligible-owner victory.
- Verify combat-use recovery through the existing battle-consumable path.
- Include at least one source acquisition in each of Westwild, Frostspine, Ashen Ruins, Mireveil, and Sunscar.

Tests can share an orchestrated production history to avoid independently re-grinding every fixture.

**Q. Test/evidence budget**

During implementation, run focused tests for the changed subsystem and its directly affected neighbors.

Required focused coverage:

- Catalog count, IDs, exact quantities, output policy, active/inactive separation.
- Every source’s actual delivery, including reward filtering.
- XP ceilings, cap behavior, and preserved historical state.
- Migration rollback, repeated startup, and prepared-settlement preservation.
- Ownership and all transaction/replay failure paths.
- Hunting participant authority.
- Price inequalities and item/gold conservation.
- Pagination, callback byte limits, message size, and locale parity.
- Existing chapter, gear, inn, gathering, and crafting regressions.

**One broad final suite is warranted** because startup schema, inventory economics, action handling, and current menus are shared infrastructure.

Run it once near readiness:

```
Working directory: rpg
python -m pytest tests
```

Do not run it after every workstream. After repairs, use affected focused tests unless a blocker materially changes shared infrastructure.

Stage 3 evidence files:

```
rpg/docs/evidence/professions_economy_v1.json
rpg/docs/epics/PROFESSIONS_ECONOMY_V1_REPORT.md
```

Evidence must record:

- Contract ID, baseline SHA, tested code commit, command, environment, exit status, and actual counts.
- Journey IDs and acquisition/action/receipt references.
- Coverage of all 28 inputs, 63 recipes, 12 professions, ten families, and three languages.
- Before/after migration comparisons and prepared-state preservation.
- Economic invariant results.
- Known limitations and failures.

Do not commit databases, credentials, real-player exports, or enormous raw traces.

If documentation/evidence is committed after the tested code commit, state both the tested commit and the final PR head, and identify the intervening documentation-only changes. Do not claim the final head was tested when it was not.

**R. Documentation updates**

The implementation PR includes all documentation changes.

- `rpg/docs/PROJECT_STATE_CURRENT.md`: reconcile PR232’s merged documentation baseline; preserve the historical compatibility excerpt and its predicates. While the Epic remains unmerged, describe it as a candidate with its actual status, not confirmed merged functionality.
- `rpg/docs/ROADMAP_CURRENT.md`: remove the stale in-progress PR232 task; replace the architecture-only proposal with the accepted/frozen Epic and subsequent implementation/review status.
- `rpg/docs/DOCS_INDEX.md`: link the contract, report, evidence, and current implementation owners.
- `rpg/docs/systems/README.md`: map profession schema, source/recipe catalogs, ownership, actions, hunting authority, and UI.
- `rpg/docs/epics/README.md`: index the new Epic.
- **New** `rpg/docs/epics/PROFESSIONS_ECONOMY_V1_SPEC.md`: retain this contract as `PEV1-1`.
- **New** `rpg/docs/epics/PROFESSIONS_ECONOMY_V1_REPORT.md`: implementation and measured acceptance results.
- **New** `rpg/docs/evidence/professions_economy_v1.json`: structured evidence.
- `rpg/docs/DECISIONS_LOG.md`: record the explicit XP policy, known craft quality, permanent learning, no cooldown, owner-only harvesting, and non-goals.

Do not rewrite foundations to make this alpha economy look like the complete level-100 design. Do not alter PR232 compatibility-retained headings or fixed-consumer markers.

Merge and deployment remain separate facts. The Draft PR must not claim either.

**S. Risks and explicit deferred items**

The frozen contract resolves ordinary product choices. Remaining risks are implementation/validation risks:

- Free repeated gathering can produce substantial gold throughput. Prices prevent conversion arbitrage, but this stage did not measure player throughput.
- Craft progression is intentionally much faster than gathering progression and capped at recipe milestones. It must be presented clearly in the UI.
- High-tier source access changes future gathering gates while preserving all owned materials and progression.
- Receipts grow with repeated actions; retention/archival is deferred.
- Migration must reject an unexpected schema rather than attempt a destructive best-effort repair.
- New source and recipe paths require actual Stage 3 evidence; static design is not proof of successful runtime behavior.

Explicitly deferred: auction, marketplace, escrow, full trading, durability/repair changes, tools, resource quality, stamina, depletion, cooldowns, talents, specializations, profession limits, craft crits/masterpieces, fragments, salvage, legendary/set/unique crafting, dungeon/world-boss recipes, seasons, guild economy, long production chains, combat rebalance, level-100 redesign, PvP reward redesign, and expanded gear gifting.


