# AI Workflow

- Status: Active
- Authority: Canonical delivery lifecycle
- Last reconciled: 2026-09-23, against `ad5435e577e45e63da2ca57af2296203d88cedd5`
Supersedes: [archived PR pipeline](archive/workflow/PR_PIPELINE.md) and the historical
Google AI / Gemini / Jules workflow material catalogued in [archive/README.md](archive/README.md)

Role labels describe responsibility, not the product or model used to perform it.
Astra and Sol may both operate through Codex while retaining separate duties.

## Lifecycle

1. **Astra — architecture / audit**
   - Verify current `main`, inventory relevant authorities and consumers, identify
     contradictions, compatibility constraints, risks, and unresolved decisions.
2. **Astra — frozen implementation contract**
   - Define scope, non-goals, authority, file/migration matrix, validation policy, and
     acceptance criteria. The contract binds the implementation candidate.
3. **Sol — implementation in one coherent Draft PR**
   - Implement the frozen contract without independent product redesign. Preserve
     unrelated work and report deviations or non-derivable decisions.
4. **Astra — independent acceptance review**
   - Review the actual diff and evidence against the frozen contract and the verified
     base/head. Approval attaches to that specific candidate.
5. **Sol — focused repair packet, if required**
   - Address only the bounded findings and update the candidate/evidence as authorized.
6. **Astra — narrow re-review**
   - Verify the repairs and affected neighbors; do not reopen unrelated design scope.
7. **User — merge after `APPROVE`**
   - The user owns the landing decision. A Draft PR is never merge authorization.
8. **Post-merge reconciliation**
   - Verify the actual merge commit and reconcile current state. Do not equate merge
     with deployment or production validation.

## Canonical statuses

`DESIGN → CONTRACT_FROZEN → IMPLEMENTING → DRAFT_REVIEW → FIX_REQUIRED → APPROVED → MERGED`

`FIX_REQUIRED` returns to `IMPLEMENTING`; a repaired candidate then returns to
`DRAFT_REVIEW`. `APPROVED` is invalidated by material unreviewed changes.

## Evidence rules

- Merge status and test evidence are separate facts.
- Historical green checks apply only to their recorded candidate and environment.
- Evidence artifacts retain exact commit/input provenance and stated limitations.
- Validation follows the frozen task policy. A docs-only contract may require static
  inspection and explicitly forbid tests or runtime execution.

## Handoff packet

Each role stops at its boundary and reports:

```text
From / To:
Lifecycle status:
Repository, branch, base and head:
Contract or reviewed candidate:
Result and scope:
Validation/evidence:
Risks and unresolved questions:
Required next action:
```

## State maintenance

[PROJECT_STATE_CURRENT.md](PROJECT_STATE_CURRENT.md) is the only merged-state summary.
A state-changing PR updates its current section without turning it into a PR log.
[ROADMAP_CURRENT.md](ROADMAP_CURRENT.md) is the only forward-priority authority.
Post-merge reconciliation must verify GitHub `main`; prose written before merge is not
proof that the merge occurred.
