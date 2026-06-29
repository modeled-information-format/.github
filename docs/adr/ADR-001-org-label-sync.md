---
title: "Org-Centralized Label Synchronization"
description: "Issue/PR labels across the org are defined once in the .github repo's root labels.yml (the github-label-sync source of truth) and applied to every repo by a reusable workflow (reusable-label-sync.yml) that each repo calls through a thin SHA-pinned caller; a repo may add an optional .github/labels.yml overlay merged over the org set. The merge step emits JSON so hex colors are never coerced to numbers."
type: adr
category: process
tags:
  - labels
  - github-label-sync
  - reusable-workflows
  - ci
  - governance
status: accepted
created: 2026-06-29
updated: 2026-06-29
author: MIF Maintainers
project: modeled-information-format
technologies:
  - github-actions
  - github-label-sync
  - python
  - pyyaml
audience:
  - developers
  - maintainers
related:
  - ADR-002-reusable-quality-gate-architecture.md
---

# ADR-001: Org-Centralized Label Synchronization

## Status

Accepted

## Context

### Background and Problem Statement

The organization runs many repositories that should share one consistent set of
issue and pull-request labels (priority, type, status, and domain labels) so that
triage, filtering, and automation behave the same everywhere. Maintaining labels
by hand per repo drifts immediately: a label renamed or recolored in one repo is
not reflected in the others, and new repos start with GitHub's default label set
rather than the org standard. The org needed a single source of truth for labels
and a mechanism that keeps every repo converged on it without per-repo manual
work, while still letting an individual repo add a few labels of its own.

### Current Limitations Before This Decision

- No canonical label definition. Each repo carried GitHub's defaults plus
  whatever ad-hoc labels had accumulated.
- No drift correction. A change to the intended label set had to be re-applied
  by hand in every repo, so repos diverged continuously.
- No clean way to express "the org standard plus a few repo-specific labels"
  without copying the whole set into each repo.

## Decision Drivers

### Primary Decision Drivers

1. **Single source of truth**: One file defines the org label set; every repo
   derives from it rather than maintaining its own copy.
2. **Automatic drift correction**: Repos re-converge on the standard on a
   schedule and whenever the label definition changes, with no manual step.
3. **Authoritative, predictable application**: The applied label set must match
   the definition exactly (names, colors, descriptions), not merely add missing
   labels, so the outcome is deterministic.

### Secondary Decision Drivers

1. **Optional per-repo extension**: A repo must be able to add a small set of
   local labels without forking the whole org set.
2. **Reuse over duplication**: Label-sync logic lives in one reusable workflow,
   not copied into each repo (consistent with the org's reusable quality-gate
   architecture, ADR-002).
3. **Supply-chain posture**: The mechanism must fit the org's fail-closed,
   SHA-pinned Actions posture and use a maintained tool rather than bespoke
   GitHub-API glue.

## Considered Options

### Option 1: Per-repo manual label management (status quo)

**Description**: Each repo owns and edits its own labels through the GitHub UI or
ad-hoc scripts.

**Advantages**:

- No shared infrastructure.

**Disadvantages**:

- Continuous drift; no convergence guarantee.
- New repos do not start from the org standard.
- No way to roll out a label change org-wide.

**Risk Assessment**:

- **Operational Risk**: High. Labels diverge by default; cross-repo automation
  that keys on label names becomes unreliable.

### Option 2: A bespoke GitHub-API script per repo

**Description**: Write a script that calls the Issues Labels API to reconcile
labels, run it in each repo.

**Advantages**:

- Full control over reconciliation behavior.

**Disadvantages**:

- Reinvents a maintained tool (`github-label-sync`), adding code to maintain and
  a larger attack surface.
- Reconciliation edge cases (renames, deletions, color/description updates) must
  be implemented and tested from scratch.

**Risk Assessment**:

- **Technical Risk**: Medium. Duplicate logic; more to get wrong than calling an
  established CLI.

### Option 3: Org-central `labels.yml` applied by a reusable workflow via github-label-sync (chosen)

**Description**: Define the org label set once in the `.github` repo's root
`labels.yml` (the documented `github-label-sync` source format). A reusable
workflow, `reusable-label-sync.yml`, fetches that file, merges an optional
repo-local overlay over it, and applies the result authoritatively with
`github-label-sync`. Every repo consumes it through a thin SHA-pinned caller that
runs weekly, on changes to the label files, and on demand.

**Advantages**:

- One source of truth; automatic weekly drift correction plus change- and
  dispatch-triggered runs.
- Authoritative application: the repo's labels are made to match (org + local)
  exactly.
- Optional overlay supports repo-specific labels without duplicating the org set.
- Uses a maintained CLI invoked via `npx` (no third-party `uses:` action to
  allow-list), fitting the org's pinned posture.

**Disadvantages**:

- Authoritative sync will remove labels not present in the merged set, so any
  label a repo wants to keep must live in the org set or the repo overlay.
- The merge step must serialize labels carefully so values such as hex colors are
  preserved as strings (see Decision Outcome).

**Risk Assessment**:

- **Technical Risk**: Low. The reusable is small and centrally maintained; the
  one serialization hazard is addressed by emitting JSON.

## Decision

Labels are centralized in `modeled-information-format/.github` and applied by a
reusable workflow:

- **Source of truth**: the `.github` repo's root `labels.yml`, in
  `github-label-sync` format (an array of `{name, color, description}`),
  currently 25 labels.
- **Reusable workflow**: `.github/workflows/reusable-label-sync.yml`
  (`workflow_call`) takes `local-labels` (default `.github/labels.yml`),
  `labels-ref` (default `HEAD` of the org `.github` repo, so callers get the
  current standard for drift correction; a tag/SHA pins a reproducible set), and
  `dry-run`. It checks out the caller, fetches the org `labels.yml`, merges the
  optional repo-local overlay over the org set (repo-local overrides by name),
  and applies the result with `github-label-sync@3.0.0` authoritatively (the
  caller's labels are made to match exactly).
- **Caller pattern**: each repo adds a thin caller
  `.github/workflows/label-sync.yml` that pins the reusable by SHA and triggers
  on `push` to the default branch limited to the label paths, a weekly
  `schedule` (`0 6 * * 1`), and `workflow_dispatch`. The job grants
  `contents: read` + `issues: write`. The `.github` repo's own
  `label-sync.yml` is the worked example other repos copy.
- **Overlay is opt-in**: a repo adds `.github/labels.yml` only if it wants extra
  labels; absent file means the org set applies as-is.

### Serialization fix (color coercion)

The merge step serializes the merged label list as **JSON**, not YAML. A hex
color such as `5319E7` is a valid `github-label-sync` color, but written as a
bare YAML scalar it parses as a float (`5319e7` = `53190000000`) under the
`js-yaml` parser that `github-label-sync` uses, and PyYAML's `safe_dump` does not
quote it. Emitting JSON (a strict subset of YAML) quotes every scalar, so colors
remain strings; `github-label-sync` reads the file via `js-yaml`, which accepts
JSON, so the downstream apply step is unchanged.

## Consequences

### Positive

1. **Convergence by default**: every repo with the caller re-applies the org
   standard weekly and whenever the label definition changes; new repos adopt the
   standard by adding one thin caller.
2. **Deterministic labels**: authoritative application means the repo's labels
   equal (org + overlay) exactly — no leftover ad-hoc labels, no missing ones.
3. **Local extension without forking**: a repo adds only its own extra labels via
   the overlay; the org set is inherited, not copied.
4. **Maintained tooling, pinned posture**: `github-label-sync` via `npx`, the
   reusable pinned by SHA in callers — no bespoke API code, no extra allow-listed
   action.

### Negative

1. **Authoritative deletion**: a label that exists in a repo but not in the
   merged set is removed. Repos must put labels they want to keep in the org set
   or their overlay.
2. **Org change requires care**: editing the org `labels.yml` propagates to every
   repo on the next run; a mistaken edit reaches all repos.

### Neutral

1. **`labels-ref` default is `HEAD`**: callers track the current org standard for
   drift correction; pinning a tag/SHA gives a reproducible set at the cost of
   manual bumps.
2. **Apply runs in the caller's context**: the reusable uses the caller's
   `GITHUB_TOKEN` (`issues: write`) to apply labels to that repo.

## Decision Outcome

Labels are defined once in the org `.github` repo and applied authoritatively to
every adopting repo by `reusable-label-sync.yml`, called through a thin
SHA-pinned `label-sync.yml` that runs weekly, on label-file changes, and on
demand. An optional `.github/labels.yml` overlay extends the org set per repo.

### Implementation

**Adopt in a repo** — add `.github/workflows/label-sync.yml`:

```yaml
name: Sync labels
on:
  push:
    branches: [main]
    paths: ['.github/labels.yml', '.github/workflows/label-sync.yml']
  schedule:
    - cron: '0 6 * * 1'
  workflow_dispatch: {}
jobs:
  labels:
    permissions:
      contents: read
      issues: write
    uses: modeled-information-format/.github/.github/workflows/reusable-label-sync.yml@<sha>
    with:
      local-labels: .github/labels.yml
```

**Apply immediately after merge** (otherwise it waits for the weekly cron or a
label-path change): `gh workflow run label-sync.yml --repo <org>/<repo>`.

**Preview without applying**: call the reusable with `dry-run: true`.

## Related Decisions

- [ADR-002: Reusable Attested Quality-Gate Architecture](ADR-002-reusable-quality-gate-architecture.md) — label-sync is one of the org's centralized reusable workflows consumed by thin SHA-pinned callers; it shares that architecture and posture.

## Links

- [Org labels runbook](https://github.com/modeled-information-format/.github/blob/main/docs/runbooks/labels-runbook.md) — the operational procedure for editing and rolling out labels.
- [github-label-sync](https://github.com/Financial-Times/github-label-sync) — the maintained CLI that applies labels authoritatively.

## More Information

- **Date:** 2026-06-29
- **Source:** `.github/workflows/reusable-label-sync.yml`, `.github/workflows/label-sync.yml`, `labels.yml`, `docs/runbooks/labels-runbook.md`.
- **Related ADRs:** ADR-002

## Audit

### 2026-06-29

**Status:** Compliant

**Findings:**

| Finding | Files | Lines | Assessment |
|---------|-------|-------|------------|
| Reusable is `workflow_call` with `local-labels` (default `.github/labels.yml`), `labels-ref` (default `HEAD`), and `dry-run` inputs | `.github/workflows/reusable-label-sync.yml` | L27, L29, L34, L39 | compliant |
| Org `labels.yml` fetched from the `.github` repo at `${LABELS_REF}`; merged with the optional repo-local overlay (repo-local overrides by name) | `.github/workflows/reusable-label-sync.yml` | L60, L65-L73 | compliant |
| Merge step emits JSON (`json.dump(..., ensure_ascii=False)`) so colors stay quoted strings rather than YAML-coercing to numbers | `.github/workflows/reusable-label-sync.yml` | L80 | compliant |
| Applied authoritatively with `github-label-sync@3.0.0`; `--dry-run` honored when `dry-run: true` | `.github/workflows/reusable-label-sync.yml` | L90-L91 | compliant |
| Only GitHub-owned `actions/checkout` is used (SHA-pinned); `github-label-sync` runs via `npx`, so no third-party `uses:` action to allow-list | `.github/workflows/reusable-label-sync.yml` | L53 | compliant |
| Org caller triggers: push to `main` limited to label paths, weekly cron `0 6 * * 1`, and `workflow_dispatch`; job grants `contents: read` + `issues: write` | `.github/workflows/label-sync.yml` | L6-L15, L19-L21 | compliant |
| Org `labels.yml` is in `github-label-sync` format and is the documented source of truth (25 labels) | `labels.yml` | L1-L8 | compliant |

**Summary:** Labels are centralized in the org `.github` repo's `labels.yml` and
applied authoritatively to every adopting repo by `reusable-label-sync.yml`,
called through a thin SHA-pinned caller that runs weekly, on label-file changes,
and on demand. The merge step emits JSON so label colors are preserved as strings.

**Action Required:** None.
