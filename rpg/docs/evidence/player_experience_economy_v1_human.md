# PXE1 human Telegram validation

Status: **NOT RUN**. No live observations, screenshots, accounts or deployment are
claimed by this implementation. Automated transport mocks are not human evidence.

Repository: danyasemennikov/rpg-bot. Baseline: PR236,
`3c5bfa62836c705a6327ce059f4e190b54ccf3e6`. Candidate branch:
`feat/pxe1-player-experience-economy-v1`. Record the exact deployed candidate SHA,
bot identity, date, device/viewport, locale and anonymized account labels A/B/C/D
when executing. Use a test bot/database; never publish credentials or player IDs.

The owner explicitly requires automated completion and one Draft PR while human
validation remains NOT RUN. Draft readiness does not establish live acceptance or
satisfy the contract's release/live validation gates. Independent review is pending.

## Frozen scenarios

Every scenario below is **NOT RUN**. Capture before/after resources, current card,
original deadline and any stale-action/restart result. Use phone and desktop in all
three locales. H09-H12 require two real accounts; H13b requires three and H13c/d
requires four. Each Chapter owner harvest requires that account's eligible victory.


| Step | Actions | Required visible result |
|---|---|---|
| H01 — fresh phone entry | A registers fresh in ru; open each permanent entry; resize/reopen Telegram | Six buttons in three rows; no giant dynamic keyboard or “menu updated” spam; meaningful welcome; none of the six loses its route |
| H02 — contextual Aster | Open Location, Nearby, board, shop, guild; inspect Help autocomplete | Local services and actual Chapter opportunity present even with no regional lead; `/journal` and `/activities` discoverable; no raw IDs |
| H03 — Chapter start | Accept First Watch; follow Journal's local route/source controls, gather herbs and fight rabbits | Free full starter tools, no pre-tool grind; one 2-minute maximum gathering card; objective increments inline; available/forming battle visible |
| H04 — full four-assignment loop | Continue Caravan, Outfitter and Homecoming through actual movement, owner harvest, craft, equip and spare sale | Each original objective/reward/location preserved; craft vest gives normal small XP, compare→Equip works, objective-only Homecoming has no0/0; active assignment absent from Available |
| H05 — readiness/finale | Complete Homecoming away from Aster; arrive, turn in, then open Journal and History | Clear route first, Turn in on arrival, immediate one finale/epilogue card, independent Regional Opportunities next; no Chapter II; History is archival; reopening doesn't grant/reannounce finale |
| H06 — local/world map | Open Map from Elmor, mine, coast and an ordinary node; switch World Map; preview discovered Elmor→Aster | Region-first defaults, current marker, readable names, preview6edges/1:45, no raw `/go id`, no active teleport |
| H07 — travel cancel | Start a multi-edge route, cancel between nodes; use old Stop after starting another trip | Visible ETA; lands at last reached node, no destination teleport; old Stop reports old result and does not stop new journey; lower menu usable |
| H08 — travel restart | Restart test bot during an edge, wait past a deadline, reopen | Persisted route resumes with at most one overdue edge and clear updated ETA; no hours of catch-up or duplicate discovery/rewards |
| H09 — real shared formation | A and B stand at the same eligible spawn. A attacks; B opens Location and Join while timer is positive | Both see the same named pack, same participant count and deadline; timer starts live combat without another click; no disappearing encounter or duplicate personal fight. Capture both accounts before/after lock |
| H10 — lock/late/leave | Repeat: B leaves during forming, then repeat with B joining just before deadline. Inspect an outsider/old Join after start | Legal prestart leave, leader transfer if A leaves, same encounter for remaining player; active roster fixed; late/stale action gets clear current status |
| H11 — pack combat | Both choose normal attack and learned skills against multiple enemies; use action→target; allow one side timeout | Compact skill list, valid target page, visible MP/cooldown, no repeated skill per enemy, same side deadline; usable summaries on phone and desktop |
| H12 — per-player result | Win a group fight; compare A/B rewards/objectives; repeat with flee/death cases in controlled test world | Correct independent eligible rewards, no final-hit race, excluded participant gains nothing under existing rule; only current owner gets one legal harvest claim, others see honest explanation; source respawns |
| H13a — two-account PvP baseline | A initiates against B in a legal test location; inspect public Location, preparation, principal escape and prohibited safe-zone initiation | Real300s preparation, both named sides, ordinary1v1 live actions and current security; actor-bound50% escape; no private hidden encounter |
| H13b — real2v1 joining | A/B are principals; A invites C; C opens local encounter and accepts A's named side. Repeat with B inviting C instead. Attempt uninvited Join and stale/other-side callback | Only approved side is joinable; invite alone does not enroll/block C; accepted C is busy and visible; accepted2v1 starts automatically, C receives controls and their attack genuinely changes the opposing actor's HP |
| H13c — real2v2 lock | A invites C, B invites D; both accept before original deadline; capture all four accounts, then all submit actions; repeat one timeout | Counts2/2 on each side, four locked real actors, two orders per side, one15s deadline, no first-order truncation, one affected-side tick, no active Join/Leave; correct action→target and waiting-ally UI |
| H13d — group consequence/recovery | Defeat A while C remains, continue to terminal; repeat with another victim and guarded/frontier material fixtures. Restart during prep, live waiting and after a side/death commit. Attempt old Join/Leave/escape | A alone respawns with correct loss/protection and no lingering busy state; C continues; survivor shares/pools and crime are per player, not final hitter; no duplication after restart; no prior deadline reset; locked allies rehydrate; old tokens cannot affect current roster |
| H13e — prep leave/escape | C accepts then leaves before lock and during delayed startup; race against start; separately have principal fail/succeed escape while ally accepted | Leave-first releases only C, no rejoin; Start-first locks C and old Leave shows combat with no free escape. Failed principal escape starts all currently accepted actors; success cancels/release all without crime refund; C cannot invoke principal escape |
| H14 — gathering/Stop/restart | Run success/failure session, Stop before/at a tick, navigate away/back, leave Telegram, then separately restart server | One edited card, ≤15 total units, finite completion, committed yield retained, no instant-click farm; server restart interrupts without offline grants |
| H15 — break/recover | With controlled durability1, gather/harvest once; buy T1 replacement; inspect ordinary T2 repair. Then all higher tools broken/no materials; use assisted repair; repeat partial-input and old callback | Last attempt succeeds then breaks;12g T1 replacement;24/120 ordinary T2 costs4wood/2iron/1coal/10g; zero-material broken T2 assisted=96g and T4=384g; partial T2 example=46g; no supplied inventory/XP or duplicate charge, no forced downgrade |
| H16 — progression/tools | On separate advanced character use T3 tool at T1/T2/T3 source and try T4; inspect commission and normal upgrade; repeat used commission | Backward compatibility, honest tool/profession gates, exact upgrade costs and one-time bootstrap requirements; no recipe/tool raw IDs and no vendor T4 shortcut |
| H17 — character/build | Spend earned points in wilderness and while gathering; try in combat; reset at hub and outside; inspect both branches | Spend works where allowed, no healing; combat denies; respec hub-only; five skills per branch; friendly mastery/investment locks, no M-codes/coefficients wall |
| H18 — shop/inventory | Buy1, change quantity, sell common1, preview All, attempt last potion/valuable/enhanced/equipped gear sale | Clear modes/prices/balance/result; no automatic All sale; correct selective confirmation/block; exact instance compare/equip, useful advanced actions preserved |
| H19 — locale sweep | Repeat menu, Map/travel, formation/combat, gathering/tool, recipe, ready quest/finale archive and skill detail in en and es; retest long ru labels | No missing keys, raw IDs, clipped critical quantities, giant row or broken plurals; phone and desktop layouts both usable |
| H20 — stale/recovery sweep | Use old callbacks after move, respawn, skill change, sale, language change and session restart; delete an activity card | Meaningful current view or exact prior receipt; no duplicate spend/reward/XP; one recoverable activity surface; no stranded battle flags |


## Session record template

- Scenario and locale: NOT RUN
- Candidate/deployed SHA: unverified
- Date, device and anonymized accounts: unrecorded
- Actions and observations: unrecorded
- Expected versus actual outcome: unrecorded
- Resource/receipt/deadline evidence: unrecorded
- Screenshot references (redacted): none
- Result: NOT RUN
- Defects and owner review: unrecorded

Keep failures and interruptions visible. Deployment, merge, automated results and
human observations are independent statuses. Do not mark a session passed from SQL
fixtures or simulated transport. RAV1's historical interrupted session is separate.
