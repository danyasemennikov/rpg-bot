"""Telegram Journal surfaces for the frozen nonlinear RAV1 catalogue."""

from __future__ import annotations

import html
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from database import get_connection, get_player
from game.i18n import get_item_name, get_location_name, t
from game.locations import get_location
from game.regional_adventures import (
    execute_regional_action, get_project_state, issue_project_choice_actions,
    issue_regional_action, list_claims, list_facts, list_pins,
)
from game.regional_catalog import (
    FACTS_BY_ID, INTERACTIONS_BY_ID, PROJECTS_BY_ID, REGIONAL_SUMMARIES,
    REGIONAL_SUMMARIES_BY_CODE, SPECIAL_TARGETS, STANDING_DELIVERIES,
)
from game.regional_opportunities import (
    VIEW_CODES, REGION_CODES, chapter_one_complete, leads, local_work, nearby,
    page as paginate, pursuits, resolved,
)


_VIEW_RE = re.compile(r"^rv:v:([hnlprsw]):(\d{1,3}):(all|ww|fs|ar|ss|mv)$")
_DETAIL_RE = re.compile(r"^rv:d:([pdiwer]):([a-z0-9_]{1,40})$")
_TAB_RE = re.compile(r"^rv:t:([pdiwer]):([a-z0-9_]{1,40}):(s|o|r)$")
_ACTION_RE = re.compile(r"^rv:a:([0-9a-f]{16})$")


def _button(text: str, data: str):
    return [InlineKeyboardButton(text[:32], callback_data=data)]


def _title(kind: str, content_id: str, lang: str) -> str:
    if kind == "region" or content_id.startswith("region_"):
        return t(f"rav1.regions.{content_id}.title", lang)
    if content_id in {"greyfang", "salt_ridge_drifter", "rav1_frostspine_n6_pass", "rav1_mireveil_n6_crosscurrent"}:
        return t(f"rav1.encounters.{content_id}.title", lang)
    if kind == "encounter":
        from game.enemy_profiles import MIXED_ENCOUNTERS
        recipe = MIXED_ENCOUNTERS.get(content_id)
        if recipe:
            labels = recipe.get("label") or {}
            return str(labels.get(lang) or labels.get("en") or content_id)
    return t(f"rav1.content.{content_id}.title", lang)


def _detail_kind(row: dict) -> str:
    return {"project":"p","discovery":"d","inspect":"d","interaction":"i","work":"w",
            "encounter":"e","region":"r"}.get(row["kind"], "i")


def build_regional_home(player: dict) -> tuple[str, InlineKeyboardMarkup]:
    lang, player_id = player.get("lang", "ru"), int(player["telegram_id"])
    pins = list_pins(player_id)
    lines = [f"🧭 <b>{t('rav1.nav.home', lang)}</b>",
             t("rav1.help.nonlinear", lang),
             t("rav1.progress.no_global", lang), "",
             f"📍 {get_location_name(player['location_id'], lang)}"]
    if pins:
        lines.append("")
        for pin in pins:
            if pin["owner_kind"] == "project":
                label = _title("project", pin["owner_id"], lang)
            elif pin["owner_kind"] == "gear":
                label = t("rav1.nav.equipment", lang)
            else:
                from game.quest_board import build_contract_title, get_hunt_contract
                contract = get_hunt_contract(pin["owner_id"])
                label = build_contract_title(contract, lang) if contract else t("rav1.services.board", lang)
            lines.append(f"📌 {html.escape(str(label))}")
    conn = get_connection()
    try:
        has_hunts = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='player_hunt_contracts'"
        ).fetchone()
        hunt = conn.execute(
            "SELECT contract_key FROM player_hunt_contracts WHERE player_id=? AND status IN ('active','completed')",
            (player_id,),
        ).fetchone() if has_hunts else None
    finally:
        conn.close()
    if hunt:
        from game.quest_board import build_contract_title, get_hunt_contract
        contract = get_hunt_contract(str(hunt["contract_key"]))
        lines += ["", f"🎯 {html.escape(str(build_contract_title(contract, lang) if contract else t('rav1.services.board', lang)))}"]
    rows = [
        [InlineKeyboardButton(t("rav1.nav.nearby", lang), callback_data="rv:v:n:0:all"),
         InlineKeyboardButton(t("rav1.nav.leads", lang), callback_data="rv:v:l:0:all")],
        [InlineKeyboardButton(t("rav1.nav.pursuits", lang), callback_data="rv:v:p:0:all"),
         InlineKeyboardButton(t("rav1.nav.regions", lang), callback_data="rv:v:r:0:all")],
        [InlineKeyboardButton(t("rav1.nav.resolved", lang), callback_data="rv:v:s:0:all"),
         InlineKeyboardButton(t("rav1.nav.work", lang), callback_data="rv:v:w:0:all")],
        [InlineKeyboardButton(t("rav1.nav.map", lang), callback_data="rv:v:r:0:all"),
         InlineKeyboardButton(t("rav1.nav.professions", lang), callback_data="pe_o:0")],
        [InlineKeyboardButton(t("rav1.nav.equipment", lang), callback_data="inv_catalog")],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(rows)


def _list_screen(player: dict, view: str, requested_page: int, region: str) -> tuple[str, InlineKeyboardMarkup]:
    lang, player_id = player.get("lang", "ru"), int(player["telegram_id"])
    if view == "n":
        title, rows = t("rav1.nav.nearby", lang), nearby(player)
    elif view == "l":
        title, rows = t("rav1.nav.leads", lang), leads(player_id, region)
    elif view == "p":
        title, rows = t("rav1.nav.pursuits", lang), pursuits(player_id)
    elif view == "r":
        title = t("rav1.nav.regions", lang)
        rows = [{"kind":"region","content_id":row["content_id"],"status":"available","data":row}
                for row in REGIONAL_SUMMARIES]
    elif view == "s":
        title = t("rav1.nav.resolved", lang)
        rows = resolved(player_id, findings=region == "ww")
    elif view == "w":
        title, rows = t("rav1.nav.work", lang), local_work(player_id)
    else:
        return build_regional_home(player)
    visible, current, pages = paginate(rows, requested_page)
    lines = [f"<b>{html.escape(str(title))}</b>"]
    buttons = []
    if not visible:
        empty_key = "empty_nearby" if view == "n" else "empty_pursuits" if view == "p" else "empty_resolved"
        lines += ["", t(f"rav1.help.{empty_key}", lang)]
    for row in visible:
        if row["kind"] == "work_link":
            label, data = t("rav1.nav.work", lang), "rv:v:w:0:all"
        elif row["kind"] == "hunt":
            from game.quest_board import build_contract_title, get_hunt_contract
            contract = get_hunt_contract(row["content_id"])
            label, data = (build_contract_title(contract, lang) if contract else t("rav1.services.board", lang)), "quest_board"
        elif row["kind"] == "gear":
            label, data = t("rav1.nav.equipment", lang), "inv_catalog"
        elif row["kind"] == "profession":
            label, data = t("rav1.nav.professions", lang), "pe_o:0"
        else:
            label = _title(row["kind"], row["content_id"], lang)
            data = f"rv:d:{_detail_kind(row)}:{row['content_id']}"
        marker = "📌 " if row.get("pinned") else ""
        status_key = ('local' if row['status']=='local' else 'remote' if row['status']=='remote'
                      else 'active' if row['status']=='active' else 'resolved' if row['status']=='resolved'
                      else 'found' if row['status']=='found' else 'busy' if row['status']=='busy'
                      else 'respawning' if row['status']=='respawning' else 'available')
        lines.append(f"\n• {marker}{html.escape(str(label))} — {t('rav1.status.' + status_key, lang)}")
        if row["kind"] == "encounter" and row["status"] in {"busy", "respawning"}:
            error_key = "busy_target" if row["status"] == "busy" else "respawning_target"
            lines.append(t(f"rav1.errors.{error_key}", lang))
            seconds = int((row.get("data") or {}).get("respawn_seconds") or 0)
            if seconds:
                lines.append(t("rav1.encounters.respawn_in", lang, seconds=seconds))
        button_row = [InlineKeyboardButton(str(label)[:32], callback_data=data)]
        if row["kind"] in {"hunt", "gear"} and row["status"] == "active":
            owner_kind = row["kind"]
            token = issue_regional_action(
                player_id, "journal", "pin",
                pin={"owner_kind":owner_kind, "owner_id":row["content_id"], "remove":bool(row.get("pinned"))},
            )
            if token:
                button_row.append(InlineKeyboardButton(
                    t("rav1.actions.unpin" if row.get("pinned") else "rav1.actions.pin", lang)[:32],
                    callback_data=f"rv:a:{token}",
                ))
        buttons.append(button_row)
    nav = []
    if current > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"rv:v:{view}:{current-1}:{region}"))
    if current + 1 < pages:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"rv:v:{view}:{current+1}:{region}"))
    if nav:
        buttons.append(nav)
    if view == "s":
        buttons.append([
            InlineKeyboardButton(t("rav1.status.resolved", lang), callback_data="rv:v:s:0:all"),
            InlineKeyboardButton(t("rav1.status.found", lang), callback_data="rv:v:s:0:ww"),
        ])
    buttons.append(_button(t("rav1.nav.home", lang), "rv:v:h:0:all"))
    return "\n".join(lines)[:3000], InlineKeyboardMarkup(buttons[:10])


def _project_detail(player: dict, project_id: str) -> tuple[str, list[list[InlineKeyboardButton]]]:
    lang, player_id = player.get("lang", "ru"), int(player["telegram_id"])
    project = PROJECTS_BY_ID[project_id]
    state, claims = get_project_state(player_id, project_id), list_claims(player_id)
    lines = [f"<b>{html.escape(str(_title('project', project_id, lang)))}</b>",
             t(f"rav1.content.{project_id}.summary", lang), "",
             t("rav1.rewards.line", lang, xp=project.reward.xp, gold=project.reward.gold,
               items=", ".join(f"{get_item_name(item, lang)} ×{qty}" for item, qty in project.reward.items) or t("rav1.rewards.none", lang))]
    rows: list[list[InlineKeyboardButton]] = []
    current_location = str(player["location_id"])
    if project_id in claims:
        lines += ["", t("rav1.status.resolved", lang)]
        choice = (state or {}).get("choices", {})
        for value in choice.values():
            lines.append(t(f"rav1.choices.{value}_after", lang))
    elif state is None:
        lines += ["", t(f"rav1.content.{project_id}.start", lang)]
        if current_location in project.start_locations:
            token = issue_regional_action(player_id, project_id, "start")
            if token:
                rows.append(_button(t("rav1.actions.start", lang), f"rv:a:{token}"))
        else:
            lines.append(t("rav1.errors.wrong_location", lang))
    else:
        step = project.steps[int(state["step_index"])]
        lines += ["", t("rav1.progress.step", lang, current=int(state["step_index"])+1, total=len(project.steps)),
                  t(f"rav1.content.{project_id}.step.{step.step_id}", lang)]
        for objective in step.objectives:
            current = int(state["progress"][f"{step.step_id}.{objective.objective_id}"])
            label = t(f"rav1.content.{project_id}.objective.{objective.objective_id}", lang)
            lines.append(t("rav1.progress.objective", lang, label=label, current=current, required=objective.required))
            if current >= objective.required or current_location not in objective.locations:
                continue
            if objective.kind == "choose":
                lines += ["", t("rav1.choices.permanent", lang)]
                tokens = issue_project_choice_actions(player_id, project_id, objective.objective_id)
                for value in objective.target["values"]:
                    if value in tokens:
                        rows.append(_button(t(f"rav1.choices.{value}", lang), f"rv:a:{tokens[value]}"))
            elif objective.kind in {"deliver", "respond"}:
                token = issue_regional_action(player_id, project_id, objective.kind, objective_id=objective.objective_id)
                if token:
                    rows.append(_button(t(f"rav1.actions.{objective.kind}", lang), f"rv:a:{token}"))
        pinned = any(row["owner_kind"] == "project" and row["owner_id"] == project_id for row in list_pins(player_id))
        token = issue_regional_action(player_id, project_id, "pin", pin={"owner_kind":"project","owner_id":project_id,"remove":pinned})
        if token:
            rows.append(_button(t("rav1.actions.unpin" if pinned else "rav1.actions.pin", lang), f"rv:a:{token}"))
    return "\n".join(lines), rows


def _interaction_detail(player: dict, content_id: str) -> tuple[str, list[list[InlineKeyboardButton]]]:
    lang, player_id = player.get("lang", "ru"), int(player["telegram_id"])
    definition = INTERACTIONS_BY_ID[content_id]
    facts, claims = list_facts(player_id), list_claims(player_id)
    lines = [f"<b>{html.escape(str(_title('interaction', content_id, lang)))}</b>",
             t(f"rav1.content.{content_id}.summary", lang)]
    rows: list[list[InlineKeyboardButton]] = []
    if definition.kind in {"discovery", "inspect"}:
        if content_id in facts:
            lines += ["", t(f"rav1.content.{content_id}.finding", lang), t("rav1.facts.already", lang)]
        elif str(player["location_id"]) == definition.location_id:
            token = issue_regional_action(player_id, content_id, "inspect")
            if token:
                rows.append(_button(t("rav1.actions.inspect", lang), f"rv:a:{token}"))
        lines += ["", t("rav1.facts.no_reward", lang)]
    elif definition.kind in {"request", "cache"}:
        lines += ["", t(f"rav1.content.{content_id}.result" if content_id in claims else f"rav1.content.{content_id}.preview", lang)]
        if content_id not in claims and str(player["location_id"]) == definition.location_id:
            if not definition.requires_fact_id or definition.requires_fact_id in facts:
                operation = "deliver" if definition.kind == "request" else "claim"
                token = issue_regional_action(player_id, content_id, operation)
                if token:
                    rows.append(_button(t(f"rav1.actions.{operation}", lang), f"rv:a:{token}"))
    return "\n".join(lines), rows


def _work_detail(player: dict, content_id: str) -> tuple[str, list[list[InlineKeyboardButton]]]:
    lang, player_id = player.get("lang", "ru"), int(player["telegram_id"])
    definition = INTERACTIONS_BY_ID[content_id]
    from game.regional_opportunities import inventory_counts
    counts = inventory_counts(player_id)
    lines = [f"<b>{html.escape(str(_title('work', content_id, lang)))}</b>",
             t(f"rav1.content.{content_id}.summary", lang),
             t(f"rav1.content.{content_id}.terms", lang), t("rav1.rewards.standing_xp", lang)]
    for item_id, required in definition.cost_items:
        owned = int(counts.get(item_id, 0))
        lines.append(t("rav1.work.owned", lang, owned=owned, required=required))
        if owned < required:
            lines.append(t("rav1.work.shortage", lang, missing=required-owned))
    rows = []
    if str(player["location_id"]) == definition.location_id:
        token = issue_regional_action(player_id, content_id, "deliver")
        if token:
            rows.append(_button(t("rav1.actions.deliver", lang), f"rv:a:{token}"))
    else:
        lines.append(t("rav1.work.remote", lang, place=get_location_name(definition.location_id, lang)))
    rows.append([
        InlineKeyboardButton(t("rav1.nav.inventory", lang)[:32], callback_data="inv_tab_all"),
        InlineKeyboardButton(t("rav1.nav.professions", lang)[:32], callback_data="pe_o:0"),
    ])
    return "\n".join(lines), rows


def _region_detail(player: dict, content_id: str) -> tuple[str, list[list[InlineKeyboardButton]]]:
    lang = player.get("lang", "ru")
    summary = next(row for row in REGIONAL_SUMMARIES if row["content_id"] == content_id)
    lines = [f"<b>{t(f'rav1.regions.{content_id}.title', lang)}</b>",
             t(f"rav1.regions.{content_id}.summary", lang), "",
             t(f"rav1.regions.{content_id}.risk", lang)]
    rows = []
    for project in PROJECTS_BY_ID.values():
        if project.region_id == summary["region_id"] and project.public:
            rows.append(_button(_title("project", project.project_id, lang), f"rv:d:p:{project.project_id}"))
    return "\n".join(lines), rows


def build_detail(player: dict, kind: str, content_id: str) -> tuple[str, InlineKeyboardMarkup]:
    if kind == "p" and content_id in PROJECTS_BY_ID:
        text, rows = _project_detail(player, content_id)
    elif kind in {"d", "i"} and content_id in INTERACTIONS_BY_ID:
        text, rows = _interaction_detail(player, content_id)
    elif kind == "w" and content_id in {entry.content_id for entry in STANDING_DELIVERIES}:
        text, rows = _work_detail(player, content_id)
    elif kind == "r" and any(row["content_id"] == content_id for row in REGIONAL_SUMMARIES):
        text, rows = _region_detail(player, content_id)
    elif kind == "e":
        from game.enemy_profiles import MIXED_ENCOUNTERS
        special = next((row for row in SPECIAL_TARGETS if row["content_id"] == content_id), None)
        recipe = MIXED_ENCOUNTERS.get(content_id)
        if not special and not recipe:
            return build_regional_home(player)
        lang = player.get("lang", "ru")
        if content_id in {"greyfang","salt_ridge_drifter","rav1_frostspine_n6_pass","rav1_mireveil_n6_crosscurrent"}:
            summary = t(f'rav1.encounters.{content_id}.summary', lang)
        else:
            summary = ", ".join(get_location_name(recipe["location_id"], lang) for _ in (0,))
        text = f"<b>{_title('encounter', content_id, lang)}</b>\n{summary}"
        rows = []
        from game.pve_live import (
            list_location_mixed_encounter_availability,
            list_location_special_target_availability,
        )
        statuses = (list_location_special_target_availability(location_id=str(player["location_id"]))
                    if special else list_location_mixed_encounter_availability(location_id=str(player["location_id"])))
        status = next((row for row in statuses if row.get("content_id") == content_id
                       or row.get("recipe_id") == content_id), None)
        if status and status["availability"] == "available":
            callback = f"fight_special_{special['key']}" if special else f"fight_mixed_{content_id}"
            rows.append(_button(t("rav1.actions.open", lang), callback))
        elif status and status["availability"] in {"busy", "respawning"}:
            key = "busy_target" if status["availability"] == "busy" else "respawning_target"
            text += "\n\n" + t(f"rav1.errors.{key}", lang)
            seconds = int(status.get("respawn_seconds") or 0)
            if seconds:
                text += "\n" + t("rav1.encounters.respawn_in", lang, seconds=seconds)
            rows.append([
                InlineKeyboardButton(t("rav1.actions.refresh", lang), callback_data=f"rv:d:e:{content_id}"),
                InlineKeyboardButton(t("rav1.nav.nearby", lang), callback_data="rv:v:n:0:all"),
            ])
    else:
        return build_regional_home(player)
    rows.append(_button(t("rav1.nav.home", player.get("lang", "ru")), "rv:v:h:0:all"))
    return text[:3000], InlineKeyboardMarkup(rows[:10])


async def handle_regional_buttons(update, context):
    query = update.callback_query
    player_row = get_player(query.from_user.id)
    if not player_row:
        await query.answer(t("rav1.errors.no_player", "ru"), show_alert=True)
        return
    player = dict(player_row)
    data, lang = str(query.data or ""), player.get("lang", "ru")
    action = _ACTION_RE.fullmatch(data)
    if action:
        try:
            result = execute_regional_action(int(player["telegram_id"]), action.group(1))
        except Exception:
            await query.answer(t("rav1.errors.temporary_atomic_failure", lang), show_alert=True)
            return
        status = str(result.get("status") or "stale_action")
        if status in {"stale_action","wrong_location","in_battle","insufficient_goods","pins_full","already_resolved","project_not_active","incompatible_step","not_discovered","unknown_content","malformed_action","incompatible_version"}:
            await query.answer(t(f"rav1.errors.{status}", lang), show_alert=True)
        else:
            await query.answer(t("rav1.status.resolved" if status == "completed" else "rav1.status.active", lang))
        player = dict(get_player(query.from_user.id))
        content_id = str((result.get("source") or {}).get("content_id") or "")
        if content_id in PROJECTS_BY_ID:
            text, keyboard = build_detail(player, "p", content_id)
        elif content_id in INTERACTIONS_BY_ID:
            kind = "w" if INTERACTIONS_BY_ID[content_id].kind == "standing" else "i"
            text, keyboard = build_detail(player, kind, content_id)
        else:
            text, keyboard = build_regional_home(player)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
        return
    match = _VIEW_RE.fullmatch(data)
    if match:
        view, raw_page, region = match.groups()
        text, keyboard = (build_regional_home(player) if view == "h"
                          else _list_screen(player, view, int(raw_page), region))
        await query.answer()
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
        return
    match = _DETAIL_RE.fullmatch(data) or _TAB_RE.fullmatch(data)
    if match:
        kind, content_id = match.group(1), match.group(2)
        text, keyboard = build_detail(player, kind, content_id)
        await query.answer()
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
        return
    text, keyboard = build_regional_home(player)
    await query.answer(t("rav1.errors.malformed_action", lang), show_alert=True)
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
