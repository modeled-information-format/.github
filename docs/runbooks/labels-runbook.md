# Labels Runbook — Org-Centralized Issue/PR Labels

This runbook defines the **org-standard label set** and how it is kept consistent
across every `modeled-information-format` repo. The labels are codified, not
hand-managed: one source of truth, applied by a reusable workflow, drift-corrected
on a schedule.

Mechanics it builds on (do not duplicate here):

- **Source of truth**: `labels.yml` at the root of this (`.github`) repo — the
  `github-label-sync` manifest. Edit labels *there*, nowhere else.
- **Apply mechanism**: `.github/workflows/reusable-label-sync.yml` (reusable;
  runs the `github-label-sync` npm CLI, pinned). A repo opts in by calling it.
- **Self-application**: `.github/workflows/label-sync.yml` applies the set to this
  repo on push to `labels.yml`, weekly (drift correction), and on demand. It is
  the worked example other repos copy.

## Taxonomy (25 labels, 6 groups)

Every label is `group: value`, lowercase, with a fixed color per group so the
board reads at a glance.

| Group | Values | Use |
| --- | --- | --- |
| `priority` | critical, high, medium, low | Triage urgency. |
| `type` | bug, feature, enhancement, documentation, security, maintenance, performance | What the work is. |
| `status` | needs-triage, in-progress, blocked, ready-for-review, approved | Where it is in flow. |
| `area` | ci-cd, dependencies, testing, infrastructure | Subsystem touched. |
| `effort` | small, medium, large | Rough size. |
| (ungrouped) | report, automated | `report` = generated/scan output; `automated` = bot-managed. |

Exact names, colors, and descriptions are authoritative in `labels.yml` — this
table is a map, not the source.

## Apply to a repo (consistently)

The set is **authoritative**: the caller's labels are made to match (org set,
optionally merged with a repo-local overlay) exactly.

```yaml
# .github/workflows/label-sync.yml in the caller repo
name: Sync labels
on:
  push: { branches: [main], paths: [.github/labels.yml] }
  schedule: [{ cron: '0 6 * * 1' }]   # weekly drift correction
  workflow_dispatch: {}
jobs:
  labels:
    permissions: { contents: read, issues: write }
    uses: modeled-information-format/.github/.github/workflows/reusable-label-sync.yml@<sha>
    with:
      local-labels: .github/labels.yml   # optional overlay, merged over the org set
      # labels-ref: HEAD                  # HEAD = current org standard; pin a SHA/tag for reproducibility
      # dry-run: true                     # preview without applying
```

- **Org set only**: omit `.github/labels.yml` in the caller (missing file = org
  set only).
- **Repo-local additions**: add a `.github/labels.yml` in the caller; it is merged
  *over* the org set (caller wins on name collisions).
- **Preview**: run with `dry-run: true` (or `workflow_dispatch`) before applying.

## Change the standard

1. Edit `labels.yml` in this repo on a PR (the branch-protection runbook governs
   that merge).
2. On merge to `main`, `label-sync.yml` re-applies to this repo; consumer repos
   pick it up on their next scheduled run (or immediately via `workflow_dispatch`)
   because `labels-ref` defaults to `HEAD`.
3. Renames/removals are destructive on consumers (sync is authoritative) — call
   them out in the PR so maintainers can re-label open issues.

## Conventions

- `group: value`, lowercase; keep one color per group (see `labels.yml`).
- Prefer reusing an existing label over inventing one; propose new labels by
  editing `labels.yml`, not by adding them ad hoc in a single repo.
- Reserve `report`/`automated` for machine-managed items so humans can filter
  them out.
