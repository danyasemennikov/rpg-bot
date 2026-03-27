import unittest

from game import balance
from game import combat


class BalanceNormalizationTests(unittest.TestCase):
    def test_melee_ranged_magic_holy_offense_profiles_scale_in_role_order(self):
        stats = {
            'strength': 32,
            'agility': 32,
            'intuition': 32,
            'vitality': 32,
            'wisdom': 32,
            'luck': 20,
        }

        base_weapon_damage = 20
        two_handed = balance.calc_final_damage(
            base_weapon_damage,
            stats,
            'melee',
            weapon_profile='sword_2h',
            damage_school='physical',
        )
        bow = balance.calc_final_damage(
            base_weapon_damage,
            stats,
            'ranged',
            weapon_profile='bow',
            damage_school='physical',
        )
        magic_staff = balance.calc_final_damage(
            base_weapon_damage,
            stats,
            'magic',
            weapon_profile='magic_staff',
            damage_school='magic',
        )
        holy_staff = balance.calc_final_damage(
            base_weapon_damage,
            stats,
            'light',
            weapon_profile='holy_staff',
            damage_school='holy',
        )
        holy_rod = balance.calc_final_damage(
            base_weapon_damage,
            stats,
            'light',
            weapon_profile='holy_rod',
            damage_school='holy',
        )
        tome = balance.calc_final_damage(
            base_weapon_damage,
            stats,
            'magic',
            weapon_profile='tome',
            damage_school='magic',
        )

        self.assertGreaterEqual(two_handed, bow)
        self.assertGreater(magic_staff, tome)
        self.assertGreater(holy_staff, holy_rod)

    def test_healing_light_and_magic_bonuses_have_explicit_caps(self):
        very_high_wisdom = 500
        very_high_intuition = 500

        heal_bonus = balance.calc_healing_bonus(very_high_wisdom)
        light_bonus = balance.calc_light_damage_bonus(very_high_wisdom)
        magic_bonus = balance.calc_school_damage_bonus_percent(
            {'intuition': very_high_intuition, 'wisdom': very_high_wisdom},
            'magic',
        )

        self.assertLessEqual(heal_bonus, balance.HEALING_SCHOOL_BONUS_CAP_PERCENT)
        self.assertLessEqual(light_bonus, balance.HOLY_SCHOOL_BONUS_CAP_PERCENT)
        self.assertLessEqual(magic_bonus, balance.MAGIC_SCHOOL_BONUS_CAP_PERCENT)

    def test_defense_mitigation_has_soft_curve_and_hard_cap(self):
        low = balance.calc_defense_mitigation_percent(20, school='physical')
        mid = balance.calc_defense_mitigation_percent(120, school='physical')
        high = balance.calc_defense_mitigation_percent(99999, school='physical')

        self.assertGreater(mid, low)
        self.assertLessEqual(high, balance.DEFENSE_MITIGATION_HARD_CAP_PERCENT)

    def test_combined_mitigation_is_multiplicative_and_capped(self):
        combined = balance.combine_mitigation_percents(40, 30)
        self.assertAlmostEqual(combined, 58.0, places=1)

        capped = balance.combine_mitigation_percents(70, 70)
        self.assertLessEqual(capped, balance.COMBINED_MITIGATION_HARD_CAP_PERCENT)

    def test_enemy_mob_attack_uses_new_mitigation_path(self):
        mob = {
            'weapon_type': 'melee',
            'damage_min': 100,
            'damage_max': 100,
            'damage_school': 'physical',
        }
        player = {
            'hp': 500,
            'agility': 30,
            'vitality': 30,
            'wisdom': 1,
            'armor_class': 'heavy',
            'offhand_profile': 'shield',
        }

        result = combat.mob_attack(mob, player, allow_dodge=False)
        self.assertGreater(result['damage'], 0)
        self.assertLess(result['damage'], 100)

    def test_crit_and_accuracy_caps_remain_explicit(self):
        self.assertLessEqual(balance.calc_crit_chance(999, 999), balance.CRIT_CHANCE_CAP_PERCENT / 100)
        self.assertEqual(balance.clamp_hit_chance(5), balance.HIT_CHANCE_MIN)
        self.assertEqual(balance.clamp_hit_chance(999), balance.HIT_CHANCE_MAX)

    def test_guaranteed_hit_still_bypasses_accuracy_evasion_check(self):
        player = {'agility': 1, 'intuition': 1}
        mob = {'level': 100, 'evasion': 1000}
        state = {}

        hit_check = combat.resolve_player_offensive_hit_check(
            player,
            mob,
            state,
            guaranteed_hit=True,
        )

        self.assertTrue(hit_check['is_hit'])
        self.assertTrue(hit_check['guaranteed_hit'])
        self.assertEqual(hit_check['outcome'], 'guaranteed_hit')

    def test_accuracy_evasion_hit_chance_stays_in_cap_window(self):
        low = balance.resolve_hit_check(accuracy_rating=10, evasion_rating=1000, rng_roll=50)
        high = balance.resolve_hit_check(accuracy_rating=1000, evasion_rating=10, rng_roll=50)

        self.assertEqual(low['hit_chance'], balance.HIT_CHANCE_MIN)
        self.assertEqual(high['hit_chance'], balance.HIT_CHANCE_MAX)


if __name__ == '__main__':
    unittest.main()
