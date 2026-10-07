"""All seventeen frozen PXE1 locale families, with legacy read aliases."""

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
    'character.skill_cost':'pxe1.skill_cost',
    'encounter.open_label':'pxe1.encounter_open',
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

ALIASES.update({
    'location.services':'pxe1.local_categories.services', 'location.exits':'pxe1.local_categories.exits',
    'location.nothing_actionable':'pxe1.local_empty', 'location.more_nearby':'pxe1.local_categories.more',
    'location.current_location':'location.title',
    'map.world':'pxe1.world_map', 'map.route_preview':'pxe1.route_preview',
    'map.no_known_route':'location.long_route_unknown', 'map.source_lead':'pxe1.source_map_hint',
    'travel.start':'pxe1.start_travel', 'travel.stop':'pxe1.stop', 'travel.remaining':'pxe1.remaining',
    'travel.position':'pxe1.travel_position', 'travel.destination':'pxe1.travel_destination',
    'travel.progress':'pxe1.travel_progress', 'travel.title':'pxe1.travel_title',
    'encounter.forming':'pxe1.combat.formation', 'encounter.participants':'pxe1.combat.participants',
    'encounter.start_failed':'pxe1.start_failed', 'encounter.resume':'pxe1.resume_activity',
    'encounter.pvp_invite':'pxe1.membership.invite',
    'encounter.pvp_join_named_side':'pxe1.membership.join_side',
    'encounter.pvp_revoke':'pxe1.revoke_invitation', 'encounter.pvp_side_count':'pxe1.membership.side_count',
    'encounter.pvp_reinvite_required':'pxe1.pvp_reinvite_required',
    'encounter.pvp_protection_blocked':'location.pvp_respawn_protection_block',
    'encounter.pvp_illegal_assist_warning':'pxe1.pvp_ally_crime_warning',
    'encounter.pvp_victory':'pxe1.result.victory', 'encounter.pvp_draw':'pxe1.result.draw',
    'encounter.pvp_cancelled':'pxe1.pvp_cancelled', 'encounter.pvp_personal_loss':'pxe1.result.lost',
    'encounter.pvp_personal_loot':'pxe1.result.received', 'encounter.pvp_personal_infamy':'pxe1.result.infamy',
    'encounter.pvp_respawn_protection':'pxe1.result.protection',
    'gather.action_label':'pxe1.gather', 'gather.preview':'pxe1.gather_preview',
    'gather.start':'pxe1.gather_start', 'gather.attempts':'pxe1.gather_progress',
    'gather.xp_total':'pxe1.gather_xp', 'gather.remaining':'pxe1.remaining', 'gather.stop':'pxe1.stop',
    'gather.completed':'pxe1.status.completed', 'gather.cancelled':'pxe1.status.cancelled',
    'gather.interrupted':'pxe1.status.interrupted', 'gather.no_eligible_resource':'pxe1.gather_locked',
    'gather.source_probability':'pxe1.gather_source_line', 'gather.tool_hint':'pxe1.gather_tool_hint',
    'gather.busy':'pxe1.gather_busy', 'gather.broken':'pxe1.gather_broken',
    'quest.progress':'pxe1.objective_feedback', 'quest.ready':'pxe1.assignment_ready',
    'quest.route_to_turn_in':'pxe1.route_to', 'quest.claimed':'pxe1.assignment_claimed',
    'quest.all_objectives':'pxe1.objectives_count', 'quest.slot_occupied':'pxe1.chapter_slot_busy',
    'journal.choose_direction':'pxe1.choose_direction', 'journal.discoveries':'pxe1.discoveries',
    'journal.opportunities':'rav1.nav.opportunities', 'journal.tracked':'rav1.nav.pursuits',
    'journal.regions':'rav1.nav.regions', 'journal.clues':'rav1.nav.leads',
    'journal.regional_completed':'rav1.nav.resolved', 'journal.local_work':'rav1.nav.work',
    'journal.history':'rav1.nav.history', 'journal.earlier_records':'pxe1.earlier_assignment',
    'journal.chapter_archive':'chapter.title', 'journal.profession_shortcut':'professions.title',
    'journal.build_shortcut':'pxe1.build_equipment',
    'chapter.complete':'pxe1.finale', 'chapter.epilogue_intro':'chapter.epilogue',
    'chapter.choose_next':'pxe1.choose_direction', 'chapter.explore_opportunities':'rav1.nav.opportunities',
    'chapter.history_replay':'chapter.title',
})

COPY.update({
    'location.nearby':('Nearby','Рядом','Cerca'),
    'location.players':('Nearby players','Игроки рядом','Jugadores cercanos'),
    'location.ready_here':('Ready to turn in here','Можно сдать здесь','Lista para entregar aquí'),
    'location.security.safe':('Safe','Безопасная','Segura'),
    'location.security.guarded':('Guarded','Под охраной','Vigilada'),
    'location.security.frontier':('Frontier','Пограничная','Fronteriza'),
    'location.security.wilderness':('Wilderness','Дикая','Salvaje'),
    'location.security.core_war':('War zone','Зона войны','Zona de guerra'),
    'map.region':('Region','Регион','Región'),
    'map.you_are_here':('You are here: {name}','Вы здесь: {name}','Estás aquí: {name}'),
    'map.visited_places':('Visited places','Посещённые места','Lugares visitados'),
    'map.undiscovered':('Not yet visited','Ещё не посещено','Aún no visitado'),
    'travel.adjacent':('Adjacent destination','Соседняя локация','Destino cercano'),
    'travel.discovered_route':('Route through visited places','Путь через посещённые места','Ruta por lugares visitados'),
    'travel.arrived':('Arrived at {name}','Прибыли: {name}','Llegaste a {name}'),
    'travel.cancelled_at':('Stopped at {name}','Остановились: {name}','Te detuviste en {name}'),
    'travel.interrupted':('Journey interrupted at {name}','Путешествие прервано: {name}','Viaje interrumpido en {name}'),
    'travel.resumed':('Journey resumed','Путешествие продолжено','Viaje reanudado'),
    'travel.route_changed':('The route changed. Open a fresh preview.','Маршрут изменился. Откройте новый предпросмотр.','La ruta cambió. Abre una nueva vista previa.'),
    'travel.flavor.neutral':('The road leads onward.','Дорога ведёт дальше.','El camino continúa.'),
    'travel.flavor.route_westwild':('The road winds between fields and woods.','Дорога петляет между полями и лесами.','El camino serpentea entre campos y bosques.'),
    'travel.flavor.route_frostspine':('The trail climbs into the mountains.','Тропа поднимается в горы.','La senda asciende hacia las montañas.'),
    'travel.flavor.route_ashen_ruins':('Ancient stones mark the road.','Древние камни отмечают путь.','Piedras antiguas marcan el camino.'),
    'travel.flavor.route_sunscar':('Heat shimmers above the dusty road.','Над пыльной дорогой дрожит зной.','El calor ondula sobre el camino polvoriento.'),
    'travel.flavor.route_mireveil':('The trail passes through misty marshes.','Тропа проходит через туманные болота.','La senda atraviesa pantanos brumosos.'),
    'encounter.starts_in':('Starts in {time}','Начало через {time}','Comienza en {time}'),
    'encounter.finished':('Combat finished','Бой завершён','Combate terminado'),
    'encounter.pvp_preparing':('PvP preparation','Подготовка PvP','Preparación de PvP'),
    'encounter.pvp_escape_attempt':('Attempt escape','Попытаться сбежать','Intentar huir'),
    'encounter.join':('Join','Присоединиться','Unirse'),
    'encounter.leave':('Leave','Выйти','Salir'),
    'encounter.roster_locked':('Participants locked','Состав зафиксирован','Participantes fijados'),
    'encounter.already_started':('Combat already started','Бой уже начался','El combate ya comenzó'),
    'encounter.respawning':('Returns in {time}','Возвращение через {time}','Regresa en {time}'),
    'encounter.preparing_retry':('Preparing combat; retrying safely.','Подготовка боя; повторная попытка.','Preparando el combate; reintentando.'),
    'encounter.leader_changed':('Group leader changed','Глава группы изменился','Cambió el líder del grupo'),
    'encounter.pvp_invitation_required':('Ask a principal to invite you to this side.','Попросите главу стороны пригласить вас.','Pide al líder que te invite a este bando.'),
    'encounter.pvp_decline':('Decline','Отказаться','Rechazar'),
    'encounter.pvp_invited_count':('Invitations: {count}','Приглашений: {count}','Invitaciones: {count}'),
    'encounter.pvp_side_full':('This side is full.','На этой стороне нет мест.','Este bando está completo.'),
    'encounter.pvp_principal_only':('Only the principal can invite allies.','Только глава стороны может приглашать союзников.','Solo el líder puede invitar aliados.'),
    'encounter.pvp_leave_preparation':('Leave','Выйти','Salir'),
    'encounter.pvp_escape_success':('Escape succeeded. This preparation ended.','Побег удался. Подготовка завершена.','La huida tuvo éxito. Esta preparación terminó.'),
    'encounter.pvp_escape_failed':('Escape failed. Combat starts now.','Побег не удался. Бой начинается сейчас.','La huida falló. El combate empieza ahora.'),
    'encounter.pvp_no_live_escape':('Escape is unavailable during live PvP.','Побег недоступен в активном PvP.','No puedes huir durante un combate PvP activo.'),
    'encounter.pvp_locked':('PvP participants locked','Состав PvP зафиксирован','Participantes de PvP fijados'),
    'encounter.pvp_waiting_for_ally':('Waiting for the ally response','Ожидание ответа союзника','Esperando la respuesta del aliado'),
    'encounter.pvp_resolving':('Resolving side orders','Обработка действий стороны','Resolviendo las acciones del bando'),
    'encounter.pvp_recent':('Recent PvP','Недавние PvP','PvP recientes'),
    'encounter.pvp_target_lost_guard':('Target vanished; this order became Guard without cost.','Цель исчезла; действие заменено на Защиту без затрат.','El objetivo desapareció; la acción pasó a Guardia sin coste.'),
    'gather.collecting':('Gathering','Сбор ресурсов','Recolectando'),
    'gather.gathered':('Gathered: {quantity}','Собрано: {quantity}','Recolectado: {quantity}'),
    'gather.restart_stopped':('Previous gathering stopped on restart. No offline attempts were granted.','Предыдущий сбор остановлен при перезапуске. Попытки за время отсутствия не начислены.','La recolección anterior se detuvo al reiniciar. No se concedieron intentos durante la desconexión.'),
    'gather.locked_result':('Result recorded','Результат записан','Resultado registrado'),
    'quest.objective_complete':('Objective complete: {name}','Цель выполнена: {name}','Objetivo completado: {name}'),
    'quest.more_changes':('More progress updates','Другие изменения прогресса','Más avances'),
    'quest.turn_in':('Turn in','Сдать задание','Entregar'),
    'quest.next_assignment':('Next assignment','Следующее задание','Siguiente misión'),
    'quest.view_next':('View next','Посмотреть следующее','Ver siguiente'),
    'quest.readiness_lost':('Requirements changed. Review the current assignment.','Условия изменились. Проверьте текущее задание.','Los requisitos cambiaron. Revisa la misión actual.'),
    'journal.current_assignment':('Current assignment','Текущее задание','Misión actual'),
    'journal.active_contract':('Active contract','Активный контракт','Contrato activo'),
})

COVERED_FAMILIES = {
    'menu':'location map journal inventory character activities welcome_status',
    'common':'back details more next previous page refresh continue already_applied screen_changed unavailable unknown_historical safe_hub_required stop_activity_first combat_blocked dead_blocked',
    'combat':'choose_action choose_target use_on_self use_on_party target_gone turn_expired waiting_for_allies last_resolution battle_details',
    'character':'profile free_points spend spend_one spend_available apply_spend spend_preview reset_hub build_equipment weapon_family mastery_required branch_points_required skill_points_required rank target_pattern cooldown_opportunities contextual_estimate empty_slot',
    'command':'start location map journal inventory profile activities stats skills build settings help',
}

COVERED_FAMILIES.update({
    'location':'nearby services exits players ready_here nothing_actionable more_nearby current_location security.safe security.guarded security.frontier security.core_war security.wilderness',
    'map':'region world you_are_here visited_places undiscovered route_preview no_known_route source_lead',
    'travel':'adjacent discovered_route start stop remaining arrived cancelled_at interrupted resumed route_changed flavor.neutral flavor.route_westwild flavor.route_frostspine flavor.route_ashen_ruins flavor.route_sunscar flavor.route_mireveil',
    'encounter':'forming starts_in join leave participants roster_locked already_started finished respawning preparing_retry start_failed leader_changed resume pvp_preparing pvp_invite pvp_invitation_required pvp_join_named_side pvp_decline pvp_revoke pvp_side_count pvp_invited_count pvp_side_full pvp_principal_only pvp_reinvite_required pvp_protection_blocked pvp_illegal_assist_warning pvp_leave_preparation pvp_escape_attempt pvp_escape_success pvp_escape_failed pvp_no_live_escape pvp_locked pvp_waiting_for_ally pvp_resolving pvp_victory pvp_draw pvp_cancelled pvp_personal_loss pvp_personal_loot pvp_personal_infamy pvp_respawn_protection pvp_recent pvp_target_lost_guard',
    'gather':'preview start collecting attempts gathered xp_total remaining stop completed cancelled interrupted restart_stopped no_eligible_resource locked_result source_probability',
    'quest':'progress objective_complete more_changes ready turn_in route_to_turn_in claimed next_assignment view_next all_objectives slot_occupied readiness_lost',
    'journal':'current_assignment active_contract opportunities choose_direction tracked regions clues regional_completed discoveries local_work history earlier_records chapter_archive profession_shortcut build_shortcut',
    'chapter':'complete epilogue_intro choose_next explore_opportunities history_replay',
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


PLURALS = {
    'character.free_points':('count',(
        ('{count} free point','{count} free points','{count} free points','{count} free points'),
        ('{count} свободное очко','{count} свободных очка','{count} свободных очков','{count} свободного очка'),
        ('{count} punto libre','{count} puntos libres','{count} puntos libres','{count} puntos libres'))),
    'combat.cooldown':('count',(
        ('Available after {count} affected-side opportunity.','Available after {count} affected-side opportunities.','Available after {count} affected-side opportunities.','Available after {count} affected-side opportunities.'),
        ('Доступно через {count} возможность затронутой стороны.','Доступно через {count} возможности затронутой стороны.','Доступно через {count} возможностей затронутой стороны.','Доступно через {count} возможности затронутой стороны.'),
        ('Disponible tras {count} oportunidad del bando afectado.','Disponible tras {count} oportunidades del bando afectado.','Disponible tras {count} oportunidades del bando afectado.','Disponible tras {count} oportunidades del bando afectado.'))),
    'character.cooldown_opportunities':('count',(
        ('Cooldown: {count} affected-side opportunity','Cooldown: {count} affected-side opportunities','Cooldown: {count} affected-side opportunities','Cooldown: {count} affected-side opportunities'),
        ('Перезарядка: {count} возможность затронутой стороны','Перезарядка: {count} возможности затронутой стороны','Перезарядка: {count} возможностей затронутой стороны','Перезарядка: {count} возможности затронутой стороны'),
        ('Recarga: {count} oportunidad del bando afectado','Recarga: {count} oportunidades del bando afectado','Recarga: {count} oportunidades del bando afectado','Recarga: {count} oportunidades del bando afectado'))),
    'character.skill_cost':('cooldown',(
        ('MP: {mana} · cooldown: {cooldown} affected-side opportunity','MP: {mana} · cooldown: {cooldown} affected-side opportunities','MP: {mana} · cooldown: {cooldown} affected-side opportunities','MP: {mana} · cooldown: {cooldown} affected-side opportunities'),
        ('МП: {mana} · перезарядка: {cooldown} возможность затронутой стороны','МП: {mana} · перезарядка: {cooldown} возможности затронутой стороны','МП: {mana} · перезарядка: {cooldown} возможностей затронутой стороны','МП: {mana} · перезарядка: {cooldown} возможности затронутой стороны'),
        ('PM: {mana} · recarga: {cooldown} oportunidad del bando afectado','PM: {mana} · recarga: {cooldown} oportunidades del bando afectado','PM: {mana} · recarga: {cooldown} oportunidades del bando afectado','PM: {mana} · recarga: {cooldown} oportunidades del bando afectado'))),
    'encounter.open_label':('count',(
        ('{name} · {count} player','{name} · {count} players','{name} · {count} players','{name} · {count} players'),
        ('{name} · {count} игрок','{name} · {count} игрока','{name} · {count} игроков','{name} · {count} игрока'),
        ('{name} · {count} jugador','{name} · {count} jugadores','{name} · {count} jugadores','{name} · {count} jugadores'))),
}
PLURAL_FORMS = ('one','few','many','other')


def plural_form(lang,number):
    if lang=='ru' and isinstance(number,int) and not isinstance(number,bool):
        n=abs(number)
        if n%10==1 and n%100!=11: return 'one'
        if 2<=n%10<=4 and not 12<=n%100<=14: return 'few'
        return 'many'
    return 'one' if number==1 else 'other'


def install_surface_keys(strings,lang):
    index=('en','ru','es').index(lang)
    additions={path:value_at(strings,source) for path,source in ALIASES.items()}
    additions.update({path:translations[index] for path,translations in COPY.items()})
    for path,(_,translations) in PLURALS.items():
        additions.update({path+'_'+form:text for form,text in zip(PLURAL_FORMS,translations[index])})
    for path,text in additions.items():
        parts=path.split('.')
        parent=strings['pxe1']
        for part in parts[:-1]:
            if not isinstance(parent.get(part,{}),dict):
                parent[part]={}
            parent=parent.setdefault(part,{})
        parent[parts[-1]]=text
