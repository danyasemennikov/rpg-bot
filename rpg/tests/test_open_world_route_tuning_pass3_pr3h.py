import unittest
from pathlib import Path

from game.locations import WORLD_LOCATIONS
from game.open_world_pack_balance import (
    collect_open_world_route_mob_ids,
    get_world_location_ids_by_route_id,
    validate_open_world_spawn_profile_placement,
)
from game.open_world_reward_alignment import validate_open_world_reward_alignment_metadata
from game.open_world_reward_pools import OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY
from game.open_world_route_balance_report import (
    build_open_world_route_balance_report,
    validate_open_world_route_balance_reports,
)
from game.open_world_pack_balance import get_world_location_ids_by_route_id
from game.mobs import MOBS
from game.skills import SKILLS


class OpenWorldRouteTuningPass3PR3HTests(unittest.TestCase):
    def _assert_major_route_tuning_state(self, route_id: str, *, allow_pack_gap: bool = False):
        report = build_open_world_route_balance_report(route_id)

        self.assertEqual(report.get('route_id'), route_id)
        self.assertFalse(report.get('is_sparse_or_stub'))
        self.assertGreaterEqual(report.get('location_count', 0), 1)

        self.assertGreater(report.get('solo_count', 0), 0)
        if allow_pack_gap:
            self.assertGreaterEqual(report.get('pack_count', 0), 0)
        else:
            self.assertGreater(report.get('pack_count', 0), 0)
        self.assertGreater(report.get('elite_anchor_count', 0), 0)

        self.assertTrue(report.get('pack_archetype_coverage_complete'))
        self.assertTrue(report.get('pack_eligibility_coverage_complete'))

        reward_category = report.get('reward_category')
        reward_profile_id = report.get('reward_profile_id')
        self.assertIn(reward_category, OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY)
        self.assertEqual(reward_profile_id, OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY[reward_category])

        warnings = set(report.get('readiness_warnings', ()))
        if allow_pack_gap:
            if report.get('pack_count', 0) == 0:
                self.assertNotIn('no_pack_mobs_on_non_stub_route', warnings)
        else:
            self.assertNotIn('no_pack_mobs_on_non_stub_route', warnings)
        self.assertNotIn('no_elite_anchors_on_non_stub_route', warnings)
        self.assertNotIn('pack_mobs_missing_archetype_metadata', warnings)
        self.assertNotIn('missing_route_gameplay_identity_profile', warnings)
        self.assertNotIn('missing_route_matchup_target_profile', warnings)
        self.assertNotIn('route_identity_tags_not_represented_by_mobs', warnings)
        self.assertTrue(report.get('gameplay_identity_id'))
        self.assertTrue(report.get('matchup_target_profile_id'))
        self.assertTrue(report.get('route_pressure_tags'))
        self.assertTrue(report.get('represented_mob_pressure_tags'))

        if report.get('rare_anchor_count', 0) == 0:
            self.assertIn('no_rare_anchors', warnings)

    def test_ashen_ruins_route_report_tuning_state(self):
        self._assert_major_route_tuning_state('route_ashen_ruins')

    def test_sunscar_route_report_tuning_state(self):
        self._assert_major_route_tuning_state('route_sunscar', allow_pack_gap=True)

    def test_mireveil_route_report_tuning_state(self):
        self._assert_major_route_tuning_state('route_mireveil')


    def test_full_alpha_routes_soft_entry_depth_pressure_guard(self):
        banned_soft_entry_tags = {'elite_bruiser', 'elite_skirmisher', 'attrition_exam', 'heavy_trade', 'route_exam'}
        for route_id in ('route_westwild', 'route_frostspine', 'route_ashen_ruins', 'route_mireveil', 'route_sunscar'):
            report = build_open_world_route_balance_report(route_id)
            depth_summary = report.get('depth_pressure_summary') or {}
            self.assertIn('soft_entry', depth_summary, msg=route_id)
            soft_tags = {str(t).strip().lower() for t in (depth_summary.get('soft_entry') or ()) if str(t).strip()}
            self.assertIn('soft_entry', soft_tags, msg=route_id)
            self.assertNotIn('route_exam', soft_tags, msg=route_id)
            self.assertFalse(soft_tags & banned_soft_entry_tags, msg=route_id)
            self.assertTrue(report.get('soft_entry_safety_ok'), msg=route_id)
            self.assertTrue(report.get('identity_pressure_present'), msg=route_id)
            self.assertTrue(report.get('build_test_pressure_present'), msg=route_id)
            self.assertTrue(report.get('route_exam_pressure_present'), msg=route_id)
            self.assertEqual(report.get('overpressure_warnings'), (), msg=route_id)

    def test_route_pressure_archetypes_and_density_shape(self):
        westwild = build_open_world_route_balance_report('route_westwild')
        ww_tags = set(westwild.get('represented_mob_pressure_tags') or ())
        self.assertIn('ambush', ww_tags)
        self.assertIn('goblin_pressure', ww_tags)
        self.assertTrue({'pack_hunter', 'moderate_pack'} & ww_tags)
        ww_depth = westwild.get('depth_pressure_summary', {})
        deep_ww_tags = set(ww_depth.get('build_testing', ())) | set(ww_depth.get('route_exam', ()))
        self.assertTrue({'goblin_pressure', 'goblin_shaman_pressure', 'leader', 'leader_pressure'} & deep_ww_tags)
        self.assertGreater(westwild['depth_pressure_density']['route_exam'], westwild['depth_pressure_density']['soft_entry'])

        frostspine = build_open_world_route_balance_report('route_frostspine')
        fs_tags = set(frostspine.get('represented_mob_pressure_tags') or ())
        self.assertTrue({'armored', 'mitigation_check', 'sustained_trade', 'heavy_trade', 'high_hp'} <= fs_tags)
        fs_depth = frostspine.get('depth_pressure_summary', {})
        self.assertTrue({'mitigation_check', 'elite_bruiser', 'heavy_trade'} & set(fs_depth.get('build_testing', ())))
        self.assertTrue({'heavy_trade', 'route_exam'} & set(fs_depth.get('route_exam', ())))
        self.assertNotIn('heavy_trade', set(frostspine.get('depth_pressure_summary', {}).get('soft_entry', ())))

        ashen = build_open_world_route_balance_report('route_ashen_ruins')
        ashen_depth = ashen.get('depth_pressure_summary', {})
        ar_tags = set(ashen.get('represented_mob_pressure_tags') or ())
        self.assertTrue({'undead', 'construct', 'caster', 'relic_guardian'} <= ar_tags)
        self.assertIn('poison_bleed_poor_target', set(ashen.get('route_pressure_tags') or ()))
        self.assertIn('undead', set(ashen_depth.get('soft_entry', ())))
        self.assertTrue({'caster', 'ethereal'} & set(ashen_depth.get('identity_visible', ())))
        self.assertTrue({'construct', 'cursed', 'relic_guardian'} & (set(ashen_depth.get('build_testing', ())) | set(ashen_depth.get('route_exam', ()))))

        mireveil = build_open_world_route_balance_report('route_mireveil')
        mv_tags = set(mireveil.get('represented_mob_pressure_tags') or ())
        self.assertTrue({'toxin', 'attrition', 'sustain_pressure', 'control_pressure'} <= mv_tags)
        self.assertIn('mirror_checked_venom', set(mireveil.get('route_pressure_tags') or ()))
        mv_depth = mireveil.get('depth_pressure_summary', {})
        self.assertFalse({'attrition_exam', 'control_pressure', 'route_exam'} & set(mv_depth.get('soft_entry', ())))
        self.assertTrue({'toxin', 'attrition', 'sustain_pressure', 'control_pressure'} & set(mv_depth.get('build_testing', ())))
        self.assertTrue({'attrition_exam', 'route_exam'} & set(mv_depth.get('route_exam', ())))

        sunscar = build_open_world_route_balance_report('route_sunscar')
        ss_tags = set(sunscar.get('represented_mob_pressure_tags') or ())
        self.assertIn('elemental', ss_tags)
        self.assertTrue({'precision', 'precision_threat', 'evasion_accuracy_check'} & ss_tags)
        self.assertTrue({'solo_pressure', 'elite_skirmisher'} & ss_tags)
        self.assertEqual(sunscar.get('pack_count'), 0)
        ss_soft = set((sunscar.get('depth_pressure_summary') or {}).get('soft_entry', ()))
        self.assertFalse({'route_exam', 'elite_skirmisher', 'burst'} & ss_soft)

    def test_sunscar_normal_spawn_counts_stay_solo_skirmish(self):
        for location_id in get_world_location_ids_by_route_id('route_sunscar'):
            profiles = WORLD_LOCATIONS[location_id].get('world_spawn_profiles') or {}
            for mob_id, profile_counts in profiles.items():
                normal_count = int((profile_counts or {}).get('normal', 0) or 0)
                self.assertLessEqual(normal_count, 1, msg=f'{location_id}:{mob_id}')

    def test_route_exam_boss_like_mobs_do_not_spawn_as_normal_triples(self):
        for route_id in ('route_westwild', 'route_frostspine', 'route_ashen_ruins', 'route_mireveil', 'route_sunscar'):
            for location_id in get_world_location_ids_by_route_id(route_id):
                profiles = WORLD_LOCATIONS[location_id].get('world_spawn_profiles') or {}
                for mob_id, profile_counts in profiles.items():
                    mob = MOBS.get(str(mob_id), {})
                    tags = {str(t).strip().lower() for t in (mob.get('combat_pressure_tags') or ())}
                    normal_count = int((profile_counts or {}).get('normal', 0) or 0)
                    if 'route_exam' in tags and ({'heavy_trade', 'elite_bruiser', 'construct', 'relic_guardian'} & tags):
                        self.assertLessEqual(normal_count, 2, msg=f'{location_id}:{mob_id}')

        self.assertLessEqual(int((WORLD_LOCATIONS['frostspine_n10'].get('world_spawn_profiles') or {}).get('troll_chief', {}).get('normal', 0) or 0), 1)
        self.assertLessEqual(int((WORLD_LOCATIONS['ashen_n3b2a1'].get('world_spawn_profiles') or {}).get('temple_guardian', {}).get('normal', 0) or 0), 2)
        self.assertLessEqual(int((WORLD_LOCATIONS['ashen_n3c2'].get('world_spawn_profiles') or {}).get('temple_guardian', {}).get('normal', 0) or 0), 2)



    def test_full_alpha_routes_have_matchup_target_metadata_only(self):
        for route_id in ('route_westwild', 'route_frostspine', 'route_ashen_ruins', 'route_mireveil', 'route_sunscar'):
            report = build_open_world_route_balance_report(route_id)
            self.assertTrue(report.get('matchup_target_profile_id'), msg=route_id)
            labels = set(report.get('matchup_target_labels') or ())
            self.assertIn('strong', labels, msg=route_id)
            if route_id != 'route_sunscar':
                self.assertIn('normal', labels, msg=route_id)
            if route_id in {'route_ashen_ruins', 'route_sunscar'}:
                self.assertTrue(any('very_hard' in x for x in labels), msg=route_id)

    def test_route_composition_and_placement_validators_remain_green(self):
        self.assertEqual(validate_open_world_spawn_profile_placement(), [])
        self.assertEqual(validate_open_world_reward_alignment_metadata(), [])
        self.assertEqual(validate_open_world_route_balance_reports(), [])

    def test_route_composition_and_live_content_remain_aligned_for_tuned_routes(self):
        for route_id in ('route_ashen_ruins', 'route_sunscar', 'route_mireveil'):
            composition_mob_ids = collect_open_world_route_mob_ids(route_id)
            location_ids = get_world_location_ids_by_route_id(route_id)
            route_live_mob_ids = set()

            for location_id in location_ids:
                location = WORLD_LOCATIONS[location_id]
                route_live_mob_ids.update(str(mob_id) for mob_id in location.get('mobs', []) if str(mob_id).strip())
                route_live_mob_ids.update(
                    str(mob_id) for mob_id in (location.get('world_spawn_profiles') or {}).keys() if str(mob_id).strip()
                )

            self.assertEqual(composition_mob_ids - route_live_mob_ids, set(), msg=route_id)
            self.assertEqual(route_live_mob_ids - composition_mob_ids, set(), msg=route_id)

    def test_reward_alignment_registry_backed_for_tuned_routes(self):
        for route_id in ('route_ashen_ruins', 'route_sunscar', 'route_mireveil'):
            report = build_open_world_route_balance_report(route_id)
            reward_category = report.get('reward_category')
            reward_profile_id = report.get('reward_profile_id')
            self.assertIn(reward_category, OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY)
            self.assertEqual(reward_profile_id, OPEN_WORLD_POOL_PROFILE_ID_BY_SOURCE_CATEGORY[reward_category])

    def test_targeting_rollout_remains_frozen_guard(self):
        expected_pattern_skills = {
            'flame_wave',
            'heavy_swing',
            'cleave_through',
            'arcane_lance',
            'hunters_mark',
            'aimed_shot',
            'piercing_arrow',
            'deadeye',
        }
        actual_pattern_skills = {
            skill_id
            for skill_id, skill in SKILLS.items()
            if skill.get('target_pattern_id') is not None
        }
        self.assertEqual(actual_pattern_skills, expected_pattern_skills)

    def test_documentation_guard(self):
        doc = Path(__file__).resolve().parent.parent.joinpath('docs', 'OPEN_WORLD_ROUTE_TUNING_PASS3.md')
        self.assertTrue(doc.exists())

        text = doc.read_text(encoding='utf-8').lower()
        self.assertIn('route_ashen_ruins', text)
        self.assertIn('route_mireveil', text)
        self.assertIn('route_sunscar', text)
        self.assertIn('no_pack_mobs_on_non_stub_route', text)
        self.assertIn('deferred to a future focused content pass', text)
        self.assertTrue('undead' in text or 'ruins' in text)
        self.assertTrue('desert' in text or 'badlands' in text)
        self.assertTrue('swamp' in text or 'mire' in text)
        self.assertIn('no reward number changes', text)
        self.assertIn('no combat formula changes', text)
        self.assertIn('no new mobs', text)
        self.assertIn('no blanket skill rollout', text)
        self.assertIn('mixed-mob packs remain future work', text)


if __name__ == '__main__':
    unittest.main()
