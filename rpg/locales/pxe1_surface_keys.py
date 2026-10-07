"""Frozen PXE1 families for the integrated navigation/build/combat surfaces.

Other frozen families are still completed by their domain integration steps.
Legacy aliases remain readable; these declared families use canonical paths.
"""

ALIASES = {
    'menu.location':'keyboard.location', 'menu.map':'keyboard.map',
    'menu.journal':'chapter.journal', 'menu.inventory':'keyboard.inventory',
    'menu.character':'keyboard.profile', 'menu.activities':'keyboard.activities',
    'menu.welcome_status':'pxe1.menu_home',
    'common.back':'common.back', 'common.details':'pxe1.details',
    'common.more':'pxe1.more', 'common.page':'gear.page', 'common.refresh':'common.refresh',
    'common.screen_changed':'gear.state_changed',
    'common.safe_hub_required':'pxe1.reset_only_hubs',
    'common.stop_activity_first':'pxe1.stop_before_trip',
    'combat.waiting_for_allies':'pxe1.combat.waiting',
    'combat.battle_details':'pxe1.details',
    'character.profile':'keyboard.profile', 'character.free_points':'pxe1.free_points',
    'character.spend_available':'pxe1.spend_all', 'character.spend_preview':'pxe1.preview',
    'character.reset_hub':'pxe1.reset_only_hubs', 'character.build_equipment':'pxe1.build_equipment',
    'character.mastery_required':'pxe1.requires_mastery',
    'character.branch_points_required':'pxe1.requires_branch',
    'character.skill_points_required':'pxe1.requires_point',
    'character.attributes':'pxe1.attributes', 'character.weapon_skills':'pxe1.weapon_skills',
    'character.mastery_level':'pxe1.mastery_level',
}
for _command in ('start','location','map','journal','inventory','profile','activities','stats','skills','build','settings','help'):
    ALIASES['command.'+_command]='pxe1.commands.'+_command

ALIASES.update({
    'tool.durability':'pxe1.tool_durability', 'tool.repair':'pxe1.repair',
    'tool.assisted_repair':'pxe1.repair_assisted', 'tool.repair_cost':'pxe1.repair_gold',
    'tool.replace_confirm':'pxe1.tool_replace_warning', 'tool.no_downgrade':'pxe1.recipe_no_downgrade',
    'tool.commission':'pxe1.commission', 'tool.commission_cost':'pxe1.commission_cost',
    'tool.commission_used':'pxe1.commission_reasons.commission_used',
    'tool.commission_visit_required':'pxe1.commission_reasons.commission_visit_required',
    'tool.commission_previous_tier':'pxe1.commission_reasons.commission_previous_tier',
    'profession.gathering':'pxe1.gathering_professions', 'profession.crafting':'pxe1.crafting_professions',
    'profession.level_xp':'professions.level', 'profession.at_cap':'professions.cap',
    'profession.known':'professions.known', 'profession.learnable':'professions.learnable',
    'profession.locked':'professions.locked', 'profession.learn':'professions.learn',
    'profession.no_xp':'professions.recipe_zero_xp', 'profession.training_ceiling':'professions.training_ceiling',
    'profession.level_up':'pxe1.profession_level', 'profession.required_recipe':'pxe1.required_recipe',
    'profession.find_inputs':'pxe1.recipe_find_inputs', 'profession.recipe_output':'professions.output_quantity',
    'profession.tool_output':'pxe1.tool_output',
})
for _tool in ('axe','pick','sickle','rod','knife'):
    ALIASES['tool.'+_tool]='pxe1.tool.'+_tool
for _tier in range(1,5):
    ALIASES['tool.tier.'+str(_tier)]='pxe1.tool.tier.'+str(_tier)

ALIASES.update({
    'inventory.compare':'gear.compare_btn', 'inventory.equip':'inventory.equip_btn',
    'inventory.use':'pxe1.combat.use', 'inventory.sources':'pxe1.sources',
    'inventory.uses':'professions.consumers', 'inventory.records':'gear.receipts_btn',
    'inventory.supplies_restrictions':'pxe1.supplies_restrictions',
    'shop.remaining':'pxe1.shop.sale_remaining',
    'tool.commission_unavailable':'pxe1.commission_reasons.commission_unavailable',
    'tool.profession_level_too_low':'pxe1.commission_reasons.profession_level_too_low',
})
for _category in ('all','gear','supplies','material','tools'):
    ALIASES['inventory.'+_category]='pxe1.inventory_categories.'+_category

# Each tuple is English, Russian, Spanish. No language falls back to another.
COPY = {
    'common.next':('Next','Далее','Siguiente'),
    'common.previous':('Previous','Назад','Anterior'),
    'common.continue':('Continue','Продолжить','Continuar'),
    'common.already_applied':('This action was already recorded.','Это действие уже записано.','Esta acción ya quedó registrada.'),
    'common.unavailable':('Unavailable here.','Здесь недоступно.','No está disponible aquí.'),
    'common.unknown_historical':('Details of this earlier record are unavailable.','Подробности этой старой записи недоступны.','Los detalles de este registro anterior no están disponibles.'),
    'common.combat_blocked':('Finish combat before this action.','Завершите бой перед этим действием.','Termina el combate antes de esta acción.'),
    'common.dead_blocked':('Your hero must recover before this action.','Персонажу нужно восстановиться перед этим действием.','Tu personaje debe recuperarse antes de esta acción.'),
    'combat.choose_action':('Choose an action.','Выберите действие.','Elige una acción.'),
    'combat.use_on_self':('Use on self','Применить к себе','Usar en ti'),
    'combat.use_on_party':('Use on party','Применить к группе','Usar en el grupo'),
    'combat.target_gone':('That target is no longer available. Open the current combat screen.','Эта цель уже недоступна. Откройте текущий экран боя.','Ese objetivo ya no está disponible. Abre la pantalla actual de combate.'),
    'combat.turn_expired':('This side deadline passed. Open the current combat screen.','Срок хода стороны истёк. Откройте текущий экран боя.','El plazo del bando terminó. Abre la pantalla actual de combate.'),
    'combat.last_resolution':('Last resolution','Последний результат хода','Última resolución'),
    'character.spend':('Spend points','Вложить очки','Asignar puntos'),
    'character.spend_one':('Spend 1 point','Вложить 1 очко','Asignar 1 punto'),
    'character.apply_spend':('Apply allocation','Подтвердить вложение','Confirmar asignación'),
    'character.weapon_family':('Weapon family','Семейство оружия','Familia de armas'),
    'character.rank':('Rank {rank}/3','Ранг {rank}/3','Rango {rank}/3'),
    'character.target_pattern':('Target: {pattern}','Цель: {pattern}','Objetivo: {pattern}'),
    'character.cooldown_opportunities':('Cooldown: {count} affected-side opportunities','Перезарядка: {count} возможностей затронутой стороны','Recarga: {count} oportunidades del bando afectado'),
    'character.contextual_estimate':('Estimate against this target; effects and defenses may change it.','Оценка против этой цели; эффекты и защита могут её изменить.','Estimación contra este objetivo; los efectos y las defensas pueden cambiarla.'),
    'character.empty_slot':('Empty slot','Пустой слот','Espacio vacío'),
    'inventory.equipped':('Equipped','Экипировано','Equipado'),
}

COPY.update({
    'tool.tier_coverage':('Covers resources up to tier {tier}.','Подходит для ресурсов до уровня инструмента {tier}.','Sirve para recursos hasta el nivel de herramienta {tier}.'),
    'tool.worn_warning':('The tool is worn. Repair or replace it soon.','Инструмент изношен. Скоро потребуется ремонт или замена.','La herramienta está gastada. Pronto necesitará reparación o sustitución.'),
    'tool.broken':('Tool broken','Инструмент сломан','Herramienta rota'),
    'tool.replace':('Replace','Заменить','Reemplazar'),
    'tool.replacement_cost':('Replacement cost: {gold} gold','Замена: {gold} золота','Sustitución: {gold} oro'),
    'tool.assisted_repair_explanation':('Your materials are used first. The guild supplies missing materials directly for gold.','Сначала расходуются ваши материалы. Недостающее гильдия добавляет напрямую за золото.','Primero se usan tus materiales. El gremio aporta directamente los que faltan a cambio de oro.'),
    'tool.assisted_repair_quote':('Guild supplies: {materials} · {gold} gold','Материалы гильдии: {materials} · {gold} золота','Aporta el gremio: {materials} · {gold} oro'),
    'tool.assisted_repair_no_gold':('Not enough gold for this guild repair quote.','Не хватает золота на этот ремонт с материалами гильдии.','No tienes oro suficiente para esta reparación con ayuda del gremio.'),
    'tool.repair_quote_changed':('This repair quote changed. Open a fresh preview.','Стоимость ремонта изменилась. Откройте новый предпросмотр.','La cotización de reparación cambió. Abre una nueva vista previa.'),
    'tool.full':('Durability is full.','Прочность полная.','La durabilidad está completa.'),
    'tool.upgrade':('Upgrade tool','Улучшить инструмент','Mejorar herramienta'),
    'tool.starter_granted':('Basic tools and their recipes are ready.','Базовые инструменты и их рецепты готовы.','Ya tienes las herramientas básicas y sus recetas.'),
    'profession.craft_one':('Craft one','Создать один предмет','Fabricar uno'),
    'profession.source_tool_gate':('Requires profession level {level} and tool tier {tier}.','Нужны уровень профессии {level} и инструмент уровня {tier}.','Requiere nivel de profesión {level} y herramienta de nivel {tier}.'),
})

COVERED_FAMILIES = {
    'menu':'location map journal inventory character activities welcome_status',
    'common':'back details more next previous page refresh continue already_applied screen_changed unavailable unknown_historical safe_hub_required stop_activity_first combat_blocked dead_blocked',
    'combat':'choose_action choose_target use_on_self use_on_party target_gone turn_expired waiting_for_allies last_resolution battle_details',
    'character':'profile free_points spend spend_one spend_available apply_spend spend_preview reset_hub build_equipment weapon_family mastery_required branch_points_required skill_points_required rank target_pattern cooldown_opportunities contextual_estimate empty_slot',
    'command':'start location map journal inventory profile activities stats skills build settings help',
}

COVERED_FAMILIES.update({
    'tool':'axe pick sickle rod knife tier.1 tier.2 tier.3 tier.4 durability tier_coverage worn_warning broken replace replacement_cost repair repair_cost assisted_repair assisted_repair_explanation assisted_repair_quote assisted_repair_no_gold repair_quote_changed full upgrade replace_confirm no_downgrade starter_granted commission commission_cost commission_used commission_visit_required commission_previous_tier',
    'profession':'gathering crafting level_xp at_cap known learnable locked learn craft_one no_xp training_ceiling level_up required_recipe find_inputs source_tool_gate recipe_output tool_output',
    'inventory':'all gear supplies material tools compare equip equipped use sources uses records',
    'shop':'buy sell quantity unit_price total remaining balance confirm_sale last_copy valuable_item quest_needed cannot_sell_equipped purchase_result sale_result starter_tools',
})


def value_at(strings,path):
    value=strings
    for part in path.split('.'):
        value=value[part]
    if not isinstance(value,str) or not value.strip():
        raise ValueError('PXE1 locale requires text: '+path)
    return value


def install_surface_keys(strings,lang):
    index=('en','ru','es').index(lang)
    additions={path:value_at(strings,source) for path,source in ALIASES.items()}
    additions.update({path:translations[index] for path,translations in COPY.items()})
    for path,text in additions.items():
        parts=path.split('.')
        parent=strings['pxe1']
        for part in parts[:-1]:
            parent=parent.setdefault(part,{})
        parent[parts[-1]]=text
