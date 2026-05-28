from pathlib import Path

from game.combat_simulation_report import build_default_alpha_simulation_report_v2_data, render_alpha_simulation_report_v2_markdown


def test_pr12_summary_section_exists():
    report = build_default_alpha_simulation_report_v2_data()
    md = render_alpha_simulation_report_v2_markdown(report)
    assert "## PR12 First Tuning Pass Summary" in md
    assert "policy_failure_guard_loop" in md
    assert "added simulation-stage pressure modifiers" in md
    assert "Changed numeric knobs:" in md
    assert "none in live systems" not in md
    assert "previous PR12 policy-sanity global overclean baseline: 88" in md
    assert "this late-stage scoped flag count is not a comparable global overclean improvement metric." in md


def test_guardian_and_paladin_no_50_turn_guard_only_traces_in_checked_in_report():
    path = Path(__file__).resolve().parents[1] / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md"
    content = path.read_text(encoding="utf-8")
    assert "| guardian_shield_1h |" in content
    assert "| holy_rod_paladin |" in content
    assert "{'normal_attack': 0, 'guard_fallback': 50}" not in content


def test_pack_proxy_sections_and_markers_remain_present():
    path = Path(__file__).resolve().parents[1] / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md"
    content = path.read_text(encoding="utf-8")
    assert "Pack / Group Simulation Preview" in content
    assert "route-stage-balanced pack preview" in content
    assert "composite_pack_pressure_v1" in content


def test_checked_in_report_tracks_guard_loop_zero_and_overclean_not_above_baseline():
    path = Path(__file__).resolve().parents[1] / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md"
    content = path.read_text(encoding="utf-8")
    assert "policy_failure_guard_loop count: 0" in content
    marker = "overclean_win: "
    pos = content.find(marker)
    assert pos != -1
    tail = content[pos + len(marker): pos + len(marker) + 4]
    number = int("".join(ch for ch in tail if ch.isdigit()))
    assert number < 88


def test_checked_in_report_has_no_fake_na_trace_row():
    path = Path(__file__).resolve().parents[1] / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md"
    content = path.read_text(encoding="utf-8")
    assert "| n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 | {} | [] |" not in content


def test_project_state_mentions_pr12_and_non_goals():
    path = Path(__file__).resolve().parents[1] / "docs" / "PROJECT_STATE_CURRENT.md"
    content = path.read_text(encoding="utf-8")
    assert "PR12: First Real Tuning Pass" in content
    assert "First Real Tuning Pass (PR12)" in content
    assert "No live group/pack combat" in content
    assert "No targeting rollout" in content
    assert "No live route/mob/skill/reward/formula tuning outside accepted tuning PRs." in content
    assert "PR12 includes simulation/reporting-only stage pressure tuning; live templates/runtime remain unchanged." in content
    assert "overclean moved from 86 to 43" not in content
    assert "global overclean candidates remain 88" in content
    assert "late-stage targeted overclean audit flags are 43" in content


def test_checked_in_report_scope_wording_uses_live_qualification():
    path = Path(__file__).resolve().parents[1] / "docs" / "ALPHA_ROUTE_CLASS_BALANCE_REPORT_V2.md"
    content = path.read_text(encoding="utf-8")
    assert "No route/mob/skill/reward/formula tuning." not in content
    assert "No live route/mob/skill/reward/formula tuning." in content
    assert "PR12 includes simulation/reporting-only stage pressure tuning." in content
