---
title: "Branch-Protection Standardization"
description: "Every org repo applies one identical default-branch protection posture via an idempotent declarative PUT script (docs/onboarding/org/branch-protection.sh): strict required status checks, one approving review with stale-review dismissal, required linear history, required conversation resolution, no force pushes or deletions, and enforce_admins=false as a deliberate solo-maintainer break-glass path. The only per-repo variable is the required-check context list — 'maximum, but only always-on' — codified in docs/runbooks/branch-protection-runbook.md."
type: adr
category: process
tags:
  - branch-protection
  - required-checks
  - governance
  - security
  - ci
status: accepted
created: 2026-06-29
updated: 2026-06-29
author: MIF Maintainers
project: modeled-information-format
technologies:
  - github
  - github-actions
  - github-rest-api
  - openssf-scorecard
audience:
  - developers
  - architects
  - maintainers
related:
  - ADR-002-reusable-quality-gate-architecture.md
  - ADR-008-github-app-ci-identity.md
---

# ADR-009: Branch-Protection Standardization

## Status

Accepted

## Context

### Background and Problem Statement

The `modeled-information-format` org runs a suite of reusable quality-gate
workflows (ADR-002): the CI jobs that they expose — CodeQL, Semgrep, Trivy,
Checkov, OSV/SCA, secrets, ShellCheck, pin-check, actionlint, and the MIF spec
validators — only protect the default branch if those jobs are actually
*required* to pass before a merge. A green check that no rule references is
advisory: a contributor (or a misconfigured automation) can still push or
merge around it. The gates are only as strong as the branch protection that
makes them mandatory.

Branch protection is per-repo state, set through the GitHub REST API (or the
repo Settings UI). Configured by hand, it drifts: one repo requires reviews and
another does not, one requires `strict` (up-to-date) status checks and another
does not, the required-context list falls out of sync with the workflows that
actually run. The org needed one canonical posture, expressed as code, that any
repo could be brought to — and re-brought to — deterministically.

This ADR records the decision to standardize default-branch protection across
the org via an idempotent declarative apply script
(`docs/onboarding/org/branch-protection.sh`) governed by a runbook
(`docs/runbooks/branch-protection-runbook.md`). It is the per-repo complement
to `docs/onboarding/org/harden.sh`, which sets org-level posture.

### Current Limitations Before This Decision

- Branch protection was set per repo by hand through the Settings UI, with no
  single source of truth and no guard against drift between repos.
- The required-status-check list was maintained manually and tended to diverge
  from the set of checks the workflows actually run on a PR — including the
  failure mode where a required context is never reported (skipped or
  path-filtered) and the PR is wedged on "Expected — waiting for status"
  forever.
- There was no documented, repeatable procedure to bring a new or existing repo
  to the org-standard posture, nor a documented relationship between that
  posture and the OpenSSF Scorecard `Branch-Protection` and `SAST` checks.

## Decision Drivers

### Primary Decision Drivers

1. **Consistency across repos**: every org repo's default branch must enforce
   the *same* posture — PR-only changes, a review, a strict up-to-date branch,
   linear history, no force-push or deletion. Per the runbook, the only thing
   that varies per repo is the required-context list; every other setting is
   identical org-wide
   (`docs/runbooks/branch-protection-runbook.md:83-85`).
2. **Idempotence and drift correction**: the apply mechanism must be a
   declarative statement of desired state that is safe to re-run and that
   corrects drift on every run, not an imperative sequence of toggles
   (`docs/onboarding/org/branch-protection.sh:12`,
   `docs/runbooks/branch-protection-runbook.md:82`).
3. **Maximum gate coverage without wedging PRs**: require every check that runs
   and concludes on every PR, and never require a check that is skipped or
   path-filtered on some PRs — a required context that does not report blocks
   the merge permanently
   (`docs/runbooks/branch-protection-runbook.md:41-53`,
   `docs/onboarding/org/branch-protection.sh:18-20`).

### Secondary Decision Drivers

1. **Solo-maintainer break-glass**: with a single maintainer a self-authored PR
   cannot collect a second-party approval. `enforce_admins=false` is a
   deliberate choice so an org admin retains an override/break-glass path while
   the recorded policy that Scorecard reads stays intact
   (`docs/runbooks/branch-protection-runbook.md:33-38`,
   `docs/onboarding/org/branch-protection.sh:51`).
2. **Scorecard alignment**: the posture directly drives the Scorecard
   `Branch-Protection` and `SAST` checks; forbidding direct-to-`main` pushes and
   requiring the SAST contexts makes every new commit SAST-covered, with the
   score converging to maximum as un-analyzed historical commits age out
   (`docs/runbooks/branch-protection-runbook.md:97-105`).
3. **Auditable, reviewable change**: expressing the posture as a checked-in
   script plus runbook means changes to the standard are reviewed like any other
   code and the worked reference invocation is version-controlled
   (`docs/onboarding/org/branch-protection.sh:22-30`).

## Considered Options

### Option 1: Per-repo manual configuration via the Settings UI (status quo)

**Description**: Each repo's maintainer sets branch protection by hand in the
GitHub Settings UI.

**Advantages**:

- No tooling to build; immediately available.

**Disadvantages**:

- No single source of truth; settings drift between repos and over time.
- The required-context list is maintained by hand and silently diverges from the
  checks the workflows actually run.
- No repeatable procedure; onboarding a repo is error-prone.

**Risk Assessment**:

- **Technical Risk**: High. Inconsistent enforcement means some repos are
  effectively unprotected; drift is invisible until a bad merge exposes it.

### Option 2: Org-wide repository ruleset

**Description**: Define a single GitHub org-level *ruleset* targeting default
branches across all repos.

**Advantages**:

- One org-level object instead of per-repo state; central management.

**Disadvantages**:

- A single org ruleset cannot express the per-repo required-context list, which
  legitimately varies (each repo has its own always-on checks). Forcing one
  shared context list either under-protects repos with more checks or wedges
  repos that do not run a listed check.
- Diverges from the existing per-repo `harden.sh` / `branch-protection.sh`
  onboarding model the org already uses
  (`docs/onboarding/org/branch-protection.sh:4-7`).

**Risk Assessment**:

- **Technical Risk**: Medium. The required-context mismatch reintroduces the
  "required check never reports" wedge the runbook explicitly guards against
  (`docs/runbooks/branch-protection-runbook.md:44-46`).

### Option 3: Idempotent declarative PUT script governed by a runbook (chosen)

**Description**: A single shell script
(`docs/onboarding/org/branch-protection.sh`) performs one declarative
`PUT /repos/{owner}/{repo}/branches/{branch}/protection` of the org-standard
desired state, taking the per-repo required-context list as positional
arguments. A runbook (`docs/runbooks/branch-protection-runbook.md`) defines the
standard, the "maximum but only always-on" required-checks policy, the
context-discovery procedure, and the relationship to Scorecard. It is the
per-repo complement to the org-level `harden.sh`.

**Advantages**:

- One identical posture across all repos; the only per-repo variable is the
  context list (`docs/runbooks/branch-protection-runbook.md:83-85`).
- Declarative PUT is idempotent — safe to re-run, corrects drift every run
  (`docs/onboarding/org/branch-protection.sh:12`).
- The standard and the discovery procedure are documented and version-controlled
  alongside the apply script.
- Self-verifies: the script prints the resulting protection state after applying
  (`docs/onboarding/org/branch-protection.sh:65-76`).

**Disadvantages**:

- The per-repo context list still has to be discovered and passed correctly; an
  over-inclusive list (a skipped/path-filtered check) wedges PRs. The runbook's
  discovery procedure and exclusion rules mitigate this
  (`docs/runbooks/branch-protection-runbook.md:54-61`).
- Requires a `gh` token with `admin:org` to run
  (`docs/onboarding/org/branch-protection.sh:9-10`).

**Risk Assessment**:

- **Technical Risk**: Low. Each invocation is an auditable declarative statement
  of the full posture; re-running converges any repo back to standard.

## Decision

The org standardizes default-branch protection across every repo via the
idempotent declarative apply script
`docs/onboarding/org/branch-protection.sh`, governed by
`docs/runbooks/branch-protection-runbook.md`. The script issues a single
`PUT /repos/$REPO/branches/$BRANCH/protection`
(`docs/onboarding/org/branch-protection.sh:46-63`) that sets the full
org-standard posture in one declarative statement:

- **Required status checks — strict**: `required_status_checks` with
  `strict: true` (the branch must be up to date with the base before merge) and
  `contexts` set to the per-repo list passed as arguments
  (`docs/onboarding/org/branch-protection.sh:50`). The list is built from the
  positional args as a JSON array, dropping blank lines
  (`docs/onboarding/org/branch-protection.sh:38-41`).
- **Required pull-request reviews**: `required_approving_review_count: 1`,
  `dismiss_stale_reviews: true`, `require_code_owner_reviews: false` — no
  direct-to-default-branch changes; a new push re-opens review
  (`docs/onboarding/org/branch-protection.sh:52-56`).
- **Required linear history**: `required_linear_history: true` — no merge
  commits; a clean, bisectable history
  (`docs/onboarding/org/branch-protection.sh:58`).
- **Required conversation resolution**: `required_conversation_resolution: true`
  — no unresolved review threads merge
  (`docs/onboarding/org/branch-protection.sh:61`).
- **No force pushes, no deletions**: `allow_force_pushes: false`,
  `allow_deletions: false` — history is append-only and the branch cannot be
  deleted (`docs/onboarding/org/branch-protection.sh:59-60`).
- **No push restrictions**: `restrictions: null`
  (`docs/onboarding/org/branch-protection.sh:57`).
- **Admins not enforced**: `enforce_admins: false` — a deliberate
  solo-maintainer break-glass path; raise to `true` once a second maintainer
  exists (`docs/onboarding/org/branch-protection.sh:51`,
  `docs/runbooks/branch-protection-runbook.md:33-38`).

The required-check context list follows the **"maximum, but only always-on"**
policy: include every job from PR-triggered, unfiltered workflows, and exclude
any check that is skipped or path-filtered on some PRs (e.g. `trivy / image`),
push-only/schedule-only workflows (`scorecard`, `deploy`), and the advisory
Copilot reviewer (`docs/runbooks/branch-protection-runbook.md:41-53`). Contexts
are discovered from a recent PR *head* SHA's check-runs, excluding skipped
conclusions (`docs/runbooks/branch-protection-runbook.md:56-61`,
`docs/onboarding/org/branch-protection.sh:18-20`).

This per-repo posture complements the org-level hardening in
`docs/onboarding/org/harden.sh` (member/repo policy, the SHA-pinning Actions
allow-list, read-only default workflow token, secret-scanning defaults). Where
`harden.sh` sets org-wide policy, `branch-protection.sh` sets the per-repo gate
that makes the reusable quality-gate jobs (ADR-002) mandatory on the default
branch (`docs/onboarding/org/branch-protection.sh:4-7`).

## Consequences

### Positive

1. **Uniform enforcement**: every repo's default branch enforces the identical
   posture; the only per-repo variable is the context list, so drift between
   repos is eliminated by construction
   (`docs/runbooks/branch-protection-runbook.md:83-85`).
2. **Drift correction on every run**: because the apply is a declarative PUT of
   the full desired state, re-running the script corrects any setting that was
   changed out-of-band (`docs/onboarding/org/branch-protection.sh:12`).
3. **Quality gates become mandatory**: the reusable-workflow jobs (ADR-002) are
   only enforced because they are listed as required strict checks here; this
   ADR is what turns advisory green checks into merge gates.
4. **Scorecard convergence**: requiring SAST contexts and forbidding
   direct-to-default-branch pushes makes every new commit SAST-covered; the
   Scorecard `SAST` ratio converges to maximum as old commits age out
   (`docs/runbooks/branch-protection-runbook.md:97-105`).

### Negative

1. **Context list must be curated per repo**: an over-inclusive required list
   (a skipped or path-filtered check) wedges PRs on "waiting for status." The
   discovery procedure and exclusion rules mitigate this but it remains a manual
   judgment per repo (`docs/runbooks/branch-protection-runbook.md:44-46`,
   `:54-61`).
2. **Admin token required**: running the script needs a `gh` token with
   `admin:org`, obtained via `gh auth refresh -h github.com -s admin:org`
   (`docs/onboarding/org/branch-protection.sh:9-10`,
   `docs/runbooks/branch-protection-runbook.md:78`).

### Neutral

1. **`enforce_admins=false` is intentional, not an oversight**: it preserves a
   maintainer break-glass path under solo maintenance. It is expected to be
   raised to `true` when a second maintainer exists, or the approval count
   dropped to `0` to allow self-merge while staying PR-gated
   (`docs/runbooks/branch-protection-runbook.md:33-38`).
2. **Required list must track workflow changes**: adding or renaming a
   PR-triggered job changes the always-on context set, so the required list must
   be re-discovered and re-applied. This is a deliberate maintenance step, not a
   defect.

## Decision Outcome

Default-branch protection is one standardized, idempotent, declarative posture
applied per repo by `docs/onboarding/org/branch-protection.sh` and governed by
`docs/runbooks/branch-protection-runbook.md`. Every default branch requires a
reviewed PR, a strict up-to-date branch, all always-on checks green, conversation
resolution, and linear history, with force pushes and deletions disabled and
`enforce_admins=false` as a deliberate break-glass path. Re-running the script
corrects drift.

### Implementation

**Apply the org-standard posture to a repo (admin token required):**

```bash
gh auth refresh -h github.com -s admin:org   # once
bash docs/onboarding/org/branch-protection.sh <owner/repo> main "<ctx>" "<ctx>" ...
```

**MIF reference set (15 required contexts):**

```text
actionlint / actionlint
pin-check / pin-check
secrets / secrets
shellcheck / sast-hooks
checkov / iac-policy
trivy / iac-license
sca / osv-scanner
sca / dependency-review
codeql / analyze
semgrep / sast-code
OKF Conformance + Lossless Round-Trip
Validate JSON-LD Projection Against Schema
Validate Ontology Files
Build Docs Site (Astro)
validate-schema-files
```

(`docs/runbooks/branch-protection-runbook.md:66-73`)

**Discover a repo's always-on contexts (paste them as args):**

```bash
gh api "/repos/<owner/repo>/commits/<pr-head-sha>/check-runs?per_page=100" \
  --jq '.check_runs[] | select(.conclusion!="skipped") | .name' | sort -u
```

(`docs/runbooks/branch-protection-runbook.md:56-61`)

**Verify the applied state:**

```bash
gh api "/repos/<owner/repo>/branches/main/protection" --jq '{
  approvals: .required_pull_request_reviews.required_approving_review_count,
  strict: .required_status_checks.strict,
  checks: (.required_status_checks.contexts | length),
  force_push: .allow_force_pushes.enabled, deletions: .allow_deletions.enabled }'
```

(`docs/runbooks/branch-protection-runbook.md:89-95`; the apply script prints an
equivalent snapshot automatically at
`docs/onboarding/org/branch-protection.sh:65-76`.)

## Related Decisions

- [ADR-002: Reusable Quality-Gate Architecture](ADR-002-reusable-quality-gate-architecture.md) -- the reusable-workflow jobs whose contexts (`codeql / analyze`, `semgrep / sast-code`, `trivy / iac-license`, …) are made mandatory by the required-status-checks list this ADR standardizes.
- [ADR-008: GitHub App CI Identity](ADR-008-github-app-ci-identity.md) -- the CI identity that runs the gated workflows; branch protection determines which of those workflow results gate a merge.

## Links

- [GitHub REST API: Branch protection](https://docs.github.com/en/rest/branches/branch-protection) -- the `PUT /repos/{owner}/{repo}/branches/{branch}/protection` endpoint the apply script calls.
- [OpenSSF Scorecard](https://github.com/ossf/scorecard) -- consumes this posture for its `Branch-Protection` and `SAST` checks.
- [Org branch-protection runbook](https://github.com/modeled-information-format/.github/blob/main/docs/runbooks/branch-protection-runbook.md) -- the governing runbook recorded by this ADR.

## More Information

- **Date:** 2026-06-29
- **Source:** `docs/onboarding/org/branch-protection.sh`, `docs/runbooks/branch-protection-runbook.md`, `docs/onboarding/org/harden.sh`.
- **Related ADRs:** ADR-002, ADR-008

## Audit

### 2026-06-29

**Status:** Compliant

**Findings:**

| Finding | Files | Lines | Assessment |
|---------|-------|-------|------------|
| Apply mechanism is a single declarative `PUT /repos/$REPO/branches/$BRANCH/protection`; documented as idempotent ("re-running is safe") | `docs/onboarding/org/branch-protection.sh` | L12, L46-L48 | compliant |
| Required status checks set to `strict: true` (up-to-date branch) with per-repo `contexts` array | `docs/onboarding/org/branch-protection.sh` | L50 | compliant |
| Required PR reviews: `required_approving_review_count: 1`, `dismiss_stale_reviews: true`, `require_code_owner_reviews: false` | `docs/onboarding/org/branch-protection.sh` | L52-L56 | compliant |
| `required_linear_history: true`, `required_conversation_resolution: true` | `docs/onboarding/org/branch-protection.sh` | L58, L61 | compliant |
| `allow_force_pushes: false`, `allow_deletions: false`, `restrictions: null` | `docs/onboarding/org/branch-protection.sh` | L57, L59-L60 | compliant |
| `enforce_admins: false` — deliberate solo-maintainer break-glass; raise to `true` with a second maintainer | `docs/onboarding/org/branch-protection.sh`, `docs/runbooks/branch-protection-runbook.md` | L51; L31, L33-L38 | compliant |
| Contexts JSON built from positional args, blank lines dropped | `docs/onboarding/org/branch-protection.sh` | L36-L41 | compliant |
| Script self-verifies by printing the resulting protection state after the PUT | `docs/onboarding/org/branch-protection.sh` | L65-L76 | compliant |
| Requires a `gh` token with `admin:org`; obtained via `gh auth refresh` | `docs/onboarding/org/branch-protection.sh` | L9-L10 | compliant |
| Org-standard settings table (PR review, strict checks, conversation resolution, linear history, no force-push/deletion, enforce_admins=false) | `docs/runbooks/branch-protection-runbook.md` | L19-L32 | compliant |
| "Maximum, but only always-on" required-checks policy; exclude skipped/path-filtered (`trivy / image`), push/schedule-only (`scorecard`, `deploy`), and advisory Copilot | `docs/runbooks/branch-protection-runbook.md` | L41-L53 | compliant |
| Context discovery uses a PR head SHA's check-runs, excluding `skipped` conclusions | `docs/runbooks/branch-protection-runbook.md`, `docs/onboarding/org/branch-protection.sh` | L56-L61; L18-L20 | compliant |
| MIF reference set of 15 required contexts documented | `docs/runbooks/branch-protection-runbook.md` | L66-L73 | compliant |
| Per-repo only the context list varies; every other setting identical org-wide | `docs/runbooks/branch-protection-runbook.md` | L83-L85 | compliant |
| Posture drives Scorecard `Branch-Protection` + `SAST` (trailing ratio, converges forward) | `docs/runbooks/branch-protection-runbook.md` | L97-L105 | compliant |
| Per-repo complement to org-level `harden.sh` (member policy, Actions allow-list, read-only token, secret-scanning defaults) | `docs/onboarding/org/branch-protection.sh`, `docs/onboarding/org/harden.sh` | L4-L7; L12-L21, L23-L38 | compliant |

**Summary:** The org standardizes default-branch protection through one
idempotent declarative PUT script (`branch-protection.sh`) governed by
`branch-protection-runbook.md`. The script sets strict required status checks,
one approving review with stale-review dismissal, required linear history and
conversation resolution, disabled force pushes and deletions, and a deliberate
`enforce_admins=false` break-glass path; the only per-repo variable is the
required-context list, curated under the "maximum, but only always-on" policy.
The posture makes the ADR-002 reusable quality-gate jobs mandatory on the
default branch and directly drives the OpenSSF Scorecard `Branch-Protection` and
`SAST` checks. It is the per-repo complement to the org-level `harden.sh`.

**Action Required:** None.
