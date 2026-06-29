---
id: 150f2462-de71-4290-867e-db3e2ebe96b7
type: procedural
created: 2026-06-28T12:14:29-04:00
namespace: _procedural/runbooks
title: "Branch Protection Runbook"
tags:
  - runbook
---

# Branch Protection Runbook — Consistent Default-Branch Gates

This runbook defines the **org-standard branch protection** every
`modeled-information-format` repo applies to its default branch, and the policy
for **requiring the maximum set of CI checks on every PR**. It is the required
posture: changes reach `main` only through a reviewed PR whose every always-on
check is green.

Mechanics it builds on (do not duplicate here):

- Org-level posture (member policy, Actions allow-list, read-only workflow token,
  secret-scanning defaults): `docs/onboarding/org/harden.sh`.
- The apply script for this runbook: `docs/onboarding/org/branch-protection.sh`
  (idempotent declarative PUT; the worked MIF example is in its header).
- The reusable quality-gate workflows whose jobs become the required checks live
  in this repo's `.github/workflows/` (sast-codeql, semgrep, trivy, checkov,
  osv/sca, secrets, shellcheck, pin-check, actionlint, …).

## The standard (every repo, default branch)

| Setting | Value | Why |
| --- | --- | --- |
| Require a pull request | yes, **1** approving review | No direct-to-`main`; a second pair of eyes (see solo-maintainer note). |
| Dismiss stale reviews | yes | A new push re-opens review. |
| Require status checks | **strict** (up-to-date branch) | PR must be rebased on latest `main`; every required check green. |
| Required checks | **all always-on PR checks** (see policy) | Maximum gate coverage. |
| Require conversation resolution | yes | No unresolved review threads merge. |
| Require linear history | yes | No merge commits; clean, bisectable `main`. |
| Allow force pushes | **no** | History is append-only. |
| Allow deletions | **no** | The branch cannot be deleted. |
| Enforce for admins | **no** | Maintainers keep a break-glass path; see note. |

**Solo-maintainer note.** With one maintainer, a self-authored PR cannot collect
a second-party approval. `enforce_admins=false` is deliberate: an org admin can
merge via admin override (or push directly for break-glass) without weakening the
recorded policy that Scorecard reads. Raise `enforce_admins` to `true` once a
second maintainer exists. To drop the unfulfillable approval instead, set
`required_approving_review_count: 0` (still PR-gated, self-merge allowed).

## Required-checks policy — "maximum, but only always-on"

Require **every check that runs and concludes on every PR.** Never require a
check that is **skipped** or **path-filtered** on some PRs: a required context
that does not report leaves the PR stuck on *"Expected — waiting for status"* and
can never merge.

- **Include**: jobs from workflows triggered `pull_request` with **no path
  filter** — in this org, `validate.yml`, `schema-check.yml`, `sast.yml`, and
  `ci.yml` are intentionally unfiltered on PRs precisely so they can be required.
- **Exclude**: `trivy / image` (skipped when no image digest is built),
  push-only or schedule-only workflows (`scorecard`, `deploy`), and the
  Copilot reviewer (advisory, not a gate).

### Discover a repo's contexts

```bash
# Use a recent PR *head* sha (not a push-to-main commit — that hides PR-only
# checks like dependency-review and shows push-only ones like scorecard/deploy):
gh api "/repos/<owner/repo>/commits/<pr-head-sha>/check-runs?per_page=100" \
  --jq '.check_runs[] | select(.conclusion!="skipped") | .name' | sort -u
```

Prefer the job-level `"<caller-job> / <reusable-job>"` contexts (e.g.
`codeql / analyze`) and the named direct jobs; they are the per-PR gates.

### MIF reference set (15 contexts)

`actionlint / actionlint`, `pin-check / pin-check`, `secrets / secrets`,
`shellcheck / sast-hooks`, `checkov / iac-policy`, `trivy / iac-license`,
`sca / osv-scanner`, `sca / dependency-review`, `codeql / analyze`,
`semgrep / sast-code`, `OKF Conformance + Lossless Round-Trip`,
`Validate JSON-LD Projection Against Schema`, `Validate Ontology Files`,
`Build Docs Site (Astro)`, `validate-schema-files`.

## Apply (consistently, any repo)

```bash
gh auth refresh -h github.com -s admin:org   # once
bash docs/onboarding/org/branch-protection.sh <owner/repo> main "<ctx>" "<ctx>" ...
```

The script is a declarative PUT of the standard above plus the contexts you pass
— re-running is safe and corrects drift. Per-repo the only thing that varies is
the contexts list (each repo's own always-on checks); every other setting is
identical across the org, which is the consistency this runbook guarantees.

## Verify

```bash
gh api "/repos/<owner/repo>/branches/main/protection" --jq '{
  approvals: .required_pull_request_reviews.required_approving_review_count,
  strict: .required_status_checks.strict,
  checks: (.required_status_checks.contexts | length),
  force_push: .allow_force_pushes.enabled, deletions: .allow_deletions.enabled }'
```

## Relationship to OpenSSF Scorecard

This posture directly drives the Scorecard `Branch-Protection` and `SAST` checks.
`SAST` is a **trailing ratio** — "of the last N commits, how many had a SAST run"
— so requiring `codeql / analyze` + `semgrep / sast-code` and forbidding
direct-to-`main` pushes makes every *new* commit SAST-covered; the score
converges to maximum as un-analyzed historical commits roll out of the window.
You cannot retroactively analyze past commits; there is no instant fix, only
guaranteed forward coverage.
