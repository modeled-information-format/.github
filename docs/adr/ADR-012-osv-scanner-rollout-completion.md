---
title: "OSV-Scanner Rollout Completion Across Org Repos"
description: "Closes an adoption gap in ADR-004's standard SCA gate by wiring reusable-sca-osv.yml into doc-site, mif-docs-plugin, and research-harness-template via one reviewed PR per repo; mnemonic-vscode and design-system remain tracked exceptions."
type: adr
conceptType: semantic
x-ontology:
  id: mif-docs
  version: "1.0.0"
  entity_type: decision-record
category: security
tags:
  - sca
  - osv
  - supply-chain
  - ci
  - security
status: accepted
created: 2026-07-01
updated: 2026-07-01
author: MIF Maintainers
project: modeled-information-format
technologies:
  - github-actions
  - osv-scanner
audience:
  - developers
  - architects
  - maintainers
related:
  - ADR-004-supply-chain-scanning.md
  - ADR-010-plugin-catalog-hub.md
---

# ADR-012: OSV-Scanner Rollout Completion Across Org Repos

## Status

Accepted

## Context

### Background and Problem Statement

ADR-004 established `reusable-sca-osv.yml` (OSV-Scanner plus the GitHub
`dependency-review` action) as the org's standard SCA gate: an independent
second opinion against the OSV vulnerability database, uploaded as SARIF to the
code-scanning hub, plus a PR merge gate on introduced vulnerable dependencies.
The reusable is SHA-pinned and free for every consuming repo to adopt as a thin
caller.

An audit of every active repo under the org, conducted on 2026-07-01, found
that adoption had stalled. Only 5 of 12 active repos actually wired the
reusable into their CI: `MIF`, `claude-code-plugins`, `mif-repo-template`,
`ontologies`, and `structured-madr`. No commit in the prior 48 hours attempted
to extend adoption further, and no repo's CI showed a disabled or malformed
reference to the reusable — the gate was simply never added to the remaining
repos' workflow files.

### Current Limitations Before This Decision

Three repos carried a `package-lock.json` (a real dependency surface) with no
SCA gate at all: `doc-site`, `mif-docs-plugin`, and `research-harness-template`.
A fourth, `mnemonic-vscode`, also carries a `package-lock.json` and lacks the
gate, but was explicitly excluded from this rollout pass by operator decision
and remains a known, tracked gap rather than an oversight. `design-system` has
no `.github/workflows/` directory at all and needs baseline CI before any
quality gate — including this one — can be added. `mnemonic` (a pure Go module)
and `modeled-information-format.github.io` carry no dependency lockfile, so the
gate does not apply to either.

## Decision Drivers

### Primary Decision Drivers

- WHEN a repo under the org carries a dependency lockfile, the repo SHALL run
  the org's standard SCA gate (`reusable-sca-osv.yml`) on every push and pull
  request against its default branch.
- WHEN a repo's SCA gate is added, the change SHALL be delivered as a reviewed
  pull request, not a direct push to the repo's default branch.
- IF a repo has no CI workflow at all, THEN this decision SHALL NOT bundle
  baseline CI setup with the SCA gate addition; baseline CI is a separate,
  prerequisite decision.

### Secondary Decision Drivers

- Reuse the exact SHA already pinned by `structured-madr`, `ontologies`, and
  `MIF` (`f83ee8058630235396f7242580570b26cf3617fa`) so no new commit-SHA trust
  decision is introduced by this rollout.
- Keep each repo's unrelated CI jobs untouched; add the `sca` job as an
  independent top-level job, not a modification of existing steps.

## Considered Options

### Option 1: Leave adoption as repo-by-repo opt-in on demand

**Description**: No forcing function; each repo's maintainer adds the gate
whenever they get to it.

**Advantages**:

- No work required now; zero authoring cost today.

**Disadvantages**:

- This is the status quo that produced the gap in the first place; nothing
  changes the outcome next time a repo's CI is scaffolded without checking
  precedent.
- Coverage stays inconsistent for an indefinite, unbounded period.

**Risk Assessment**:

- **Technical Risk**: Low. No new surface introduced.
- **Schedule Risk**: N/A. No work scheduled.
- **Ecosystem Risk**: High. The gap persists and is likely to recur.

### Option 2: A scheduled org-wide automation that force-adds the job to every repo with a lockfile

**Description**: Extend a pattern similar to `plugin-catalog-update-hub.yml`
(ADR-010): a scheduled job across all org repos that detects a missing SCA
gate and opens an auto-merge PR.

**Advantages**:

- Self-healing: a future repo added without the gate would be caught
  automatically rather than depending on another manual audit.

**Disadvantages**:

- A new cross-repo write surface, a new App or token scope, a new failure
  mode to operate — as seen when `plugin-catalog-update-hub.yml`'s own
  auto-merge needed a branch-protection bypass grant to actually land a PR.
- Building and testing a second cross-repo automation is real engineering
  work for a one-time backlog of three repos.

**Risk Assessment**:

- **Technical Risk**: Medium. New automation surface with its own failure
  modes to operate.
- **Schedule Risk**: Medium. Disproportionate build cost for today's backlog
  size.
- **Ecosystem Risk**: Low once built, but the investment is not justified by
  the scope of the actual problem today.

### Option 3: Manual, audited one-time rollout PRs to the specific repos found missing the gate (chosen)

**Description**: Add the `sca` job directly to `doc-site`, `mif-docs-plugin`,
and `research-harness-template`'s existing `ci.yml` files, matching the exact
pattern already proven in `structured-madr`/`ontologies`/`MIF`, and open one
PR per repo through each repo's normal review process.

**Advantages**:

- The pattern is already proven in five other repos; no new YAML shape, no
  new pinned SHA to trust.
- Each repo's own branch protection and review process still gates the
  change; no new automation surface to operate or maintain.

**Disadvantages**:

- Purely manual; does not prevent the same gap from recurring if a future
  repo's CI is scaffolded without checking this precedent.

**Risk Assessment**:

- **Technical Risk**: Low. The pattern is already proven in five other repos.
- **Schedule Risk**: Low. Three small, independent, single-file PRs.
- **Ecosystem Risk**: Low. No new automation surface to operate or maintain.

## Decision

Wire `modeled-information-format/.github/.github/workflows/reusable-sca-osv.yml`
(pinned at `f83ee8058630235396f7242580570b26cf3617fa`, `fail-on-severity: high`)
into `doc-site`, `mif-docs-plugin`, and `research-harness-template` as a new
top-level `sca` job in each repo's existing `ci.yml`, using the identical
permissions block (`actions: read`, `contents: read`, `security-events: write`,
`pull-requests: write`) and `with:` input already used in `structured-madr`.
Each change lands as its own pull request against the target repo's default
branch; none is merged as part of this decision — each goes through that
repo's normal review and required-checks process.

`mnemonic-vscode` is intentionally excluded from this rollout pass.
`design-system` is intentionally excluded pending baseline CI.

## Consequences

### Positive

- Dependency vulnerability coverage now spans every active repo in the org
  that carries a lockfile, except the two explicitly tracked exceptions.
- No new commit-SHA trust decision: all three rollout PRs reuse the exact pin
  already trusted by three other repos.
- Each repo's own review process remains the merge gate; this decision adds no
  new bypass or automation surface.

### Negative

- This was a manual, one-time catch-up. The same drift can recur if a new
  repo's CI is scaffolded without checking this precedent — nothing in this
  decision prevents that on its own.
- Three separate PRs must each independently pass their repo's existing CI
  before merge; a repo-specific failure in one does not block the others, but
  also is not resolved by this decision.

### Neutral

- `mnemonic-vscode` remains a known, deliberately deferred gap, not an
  oversight, following an explicit operator decision to exclude it from this
  pass.

## Decision Outcome

The decision meets its objective — closing the specific, audited gap — without
introducing new infrastructure. The identified follow-up risk (recurrence via
future un-scaffolded CI) is not mitigated here; it is a candidate for a future
decision, most plausibly by extending the `plugin-catalog-update-hub.yml`
pattern (ADR-010) or by adding this gate to a repo-scaffolding checklist,
should the same gap recur.

## Related Decisions

- [ADR-004](ADR-004-supply-chain-scanning.md) — established
  `reusable-sca-osv.yml` as the org's standard SCA gate; this decision closes
  a gap in its adoption, it does not change the gate itself.
- [ADR-010](ADR-010-plugin-catalog-hub.md) — the scheduled cross-repo
  automation pattern considered and rejected as disproportionate for this
  backlog (Option 2), noted here as the precedent to revisit if the gap
  recurs.

## Links

- `modeled-information-format/.github/.github/workflows/reusable-sca-osv.yml`
- `modeled-information-format/doc-site` PR: ci: add OSV-Scanner SCA gate
- `modeled-information-format/mif-docs-plugin` PR: ci: add OSV-Scanner SCA gate
- `modeled-information-format/research-harness-template` PR: ci: add
  OSV-Scanner SCA gate

## More Information

The rollout was triggered by a manual audit rather than a scheduled process;
this ADR itself is the record of that one-time catch-up, not of a recurring
mechanism.

## Audit

### 2026-07-01

**Status:** Partial

**Findings:**

| Finding | Files | Assessment |
|---------|-------|------------|
| `sca` job added to `doc-site/.github/workflows/ci.yml`, matching the structured-madr pattern | `doc-site` PR | compliant |
| `sca` job added to `mif-docs-plugin/.github/workflows/ci.yml`, matching the structured-madr pattern | `mif-docs-plugin` PR | compliant |
| `sca` job added to `research-harness-template/.github/workflows/ci.yml`, matching the structured-madr pattern | `research-harness-template` PR | compliant |
| `mnemonic-vscode` still missing the gate | (tracked gap) | non-compliant, deliberate |
| `design-system` has no CI workflow to add the gate to | (tracked gap) | non-compliant, deferred |

**Summary:** Three of the four repos found missing the standard SCA gate now
carry it, each via an independent, unmerged pull request awaiting normal
review. `mnemonic-vscode` remains excluded by operator decision;
`design-system` remains blocked on baseline CI setup, out of scope here.

**Action Required:** Review and merge the three open pull requests; decide
separately whether and when to bring `mnemonic-vscode` and `design-system`
into scope.
