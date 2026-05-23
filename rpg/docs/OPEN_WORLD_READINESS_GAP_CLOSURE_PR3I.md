# Open-world Readiness Gap Closure (PR 3I)

This pass follows PR 3H and consolidates open-world readiness gaps before numeric PvE tuning.

## What this pass does
- closes actionable readiness gaps where safe using existing live route-local content;
- adds a consolidated readiness-gap report layer to summarize actionable vs deferred warnings;
- keeps route/report/placement/reward validators green.

## Sunscar pack pressure status
- `route_sunscar` pack pressure remains a tracked future-content-required gap in PR 3I.
- Current route-local `scorpion` normal spawn counts are 1 per location, which cannot create same-group pack pressure under current runtime pack claim semantics.
- No unsafe spawn-probability/content topology changes were made in this pass.

## Scope guardrails
- no reward number changes;
- no reward formula changes;
- no combat formula changes;
- no mob stat changes;
- no route topology changes;
- no spawn probability changes;
- no mixed-mob packs;
- no blanket skill rollout;
- no UI/repositioning changes.

## Remaining deferred diagnostics
- `no_rare_anchors` warnings remain deferred readiness gaps unless route-local rare content already exists and must be represented.

Unknown readiness warning IDs are treated as actionable/invalid until explicitly classified.
