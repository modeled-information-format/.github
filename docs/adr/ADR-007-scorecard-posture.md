---
title: "OpenSSF Scorecard Posture Assessment"
description: "The org runs OpenSSF Scorecard as a central reusable workflow (reusable-scorecard.yml) for repository security-posture assessment. The analysis job requests security-events:write, id-token:write, contents:read, and actions:read; uploads SARIF to the code-scanning hub; and publishes results to the OpenSSF REST API by default. Scorecard authenticates with the run's GITHUB_TOKEN, optionally upgrading to an org CI App installation token (administration:read) for the Branch-Protection check. All actions are SHA-pinned."
type: adr
category: security
tags:
  - scorecard
  - openssf
  - posture
  - supply-chain
  - security
status: accepted
created: 2026-06-29
updated: 2026-06-29
author: MIF Maintainers
project: modeled-information-format
technologies:
  - github-actions
  - openssf-scorecard
  - sarif
  - codeql
  - sigstore
audience:
  - developers
  - architects
  - maintainers
related:
  - ADR-002-reusable-quality-gate-architecture.md
  - ADR-005-signing-attestation-verification.md
---

# ADR-007: OpenSSF Scorecard Posture Assessment

## Status

Accepted

## Context

### Background and Problem Statement

The org publishes a specification, JSON Schemas, and supporting tooling that
downstream consumers pin and depend on. Beyond per-finding gates (SAST, SCA,
secrets), the org needs a single, continuously refreshed measure of each
repository's *security posture*: whether branch protection is configured,
whether code review is enforced, whether workflow token permissions are
minimal, whether dependencies are pinned, whether releases are signed, and
similar heuristics. OpenSSF Scorecard computes exactly these 0-10 heuristics
and emits the result as SARIF.

Two problems had to be solved together. First, the posture check must run on a
schedule and on the events that change posture (default-branch pushes and
branch-protection-rule changes), not only on pull requests, because posture
drifts independently of code changes. Second, Scorecard's Branch-Protection
heuristic cannot be scored accurately from the default `GITHUB_TOKEN`, which
cannot read branch-protection settings; without elevated read access the check
is capped regardless of the repository's actual configuration.

This ADR records the decision to run Scorecard as one of the org's central
reusable workflows (`reusable-scorecard.yml`) that every repository calls,
rather than copying Scorecard wiring into each repo. It builds on the reusable
quality-gate architecture (ADR-002) and shares the SARIF-as-attestation-seam
pattern with the signing/attestation work (ADR-005).

### Current Limitations Before This Decision

- No continuous, machine-readable posture signal existed for org
  repositories; posture was assessed ad hoc, if at all.
- The default `GITHUB_TOKEN` cannot read branch-protection settings, so any
  naive Scorecard wiring would under-report the Branch-Protection heuristic.
- Without a published result, posture was not externally verifiable and carried
  no public badge.

## Decision Drivers

### Primary Decision Drivers

1. **Continuous posture visibility**: Posture must be re-measured on the events
   that change it (default-branch push, branch-protection-rule change) and on a
   weekly schedule, independent of pull-request activity.
2. **Accurate Branch-Protection scoring**: The workflow must be able to read
   real branch-protection settings (`administration:read`) so the heuristic
   reflects actual configuration, while still functioning when that elevated
   read is unavailable.
3. **Centralized, SHA-pinned implementation**: Scorecard wiring lives in one
   reusable workflow that callers invoke by full 40-character SHA, consistent
   with the org's fail-closed, SHA-pinned posture (ADR-002).

### Secondary Decision Drivers

1. **Code-scanning integration**: Posture findings should land in the GitHub
   code-scanning hub as SARIF so they surface alongside SAST results.
2. **Public attestation and badge**: Publishing results to the OpenSSF REST API
   yields a public posture attestation and badge, requiring `id-token: write`.
3. **Attestation seam reuse**: The SARIF should be exposed as a downloadable
   artifact so the signing/attestation seam (ADR-005) can sign it bound to a
   release subject.

## Considered Options

### Option 1: No posture assessment (status quo)

**Description**: Rely solely on per-finding gates (SAST, SCA, secrets) and no
aggregate posture measure.

**Advantages**:

- Zero additional workflow surface.

**Disadvantages**:

- No aggregate, continuously refreshed posture signal; configuration drift
  (e.g. branch protection disabled) goes unmeasured.
- No public posture attestation or badge.

**Risk Assessment**:

- **Technical Risk**: Medium. Posture regressions are invisible until they
  cause a downstream incident.

### Option 2: Per-repo copy of Scorecard wiring

**Description**: Copy a Scorecard job into each repository's CI rather than
calling a central reusable workflow.

**Advantages**:

- Each repo is self-contained.

**Disadvantages**:

- Duplicates the Branch-Protection App-token logic, the SARIF upload, and the
  artifact-exposure step across every repo, so a fix must be applied N times.
- Diverges over time; the org loses a single audited implementation.

**Risk Assessment**:

- **Technical Risk**: Medium. Maintenance burden and drift between copies.

### Option 3: Central reusable Scorecard workflow with App-token Branch-Protection read (chosen)

**Description**: Implement Scorecard once as `reusable-scorecard.yml`
(`workflow_call`). Every repo calls it by SHA pin, granting
`security-events: write`, `id-token: write`, `contents: read`, and
`actions: read` to the `analysis` job. The workflow optionally mints an org CI
App installation token (so the Branch-Protection check is scored from real
settings via `administration:read`) and falls back to the run's `GITHUB_TOKEN`
when no App private key is supplied. SARIF is uploaded to code-scanning and also
exposed as an artifact for the attestation seam. `publish-results` defaults to
`true`.

**Advantages**:

- One audited implementation; callers are thin and SHA-pinned.
- Branch-Protection scored accurately when the App key is present, with a
  graceful soft-fail fallback when it is not.
- SARIF integrates with code-scanning and feeds the attestation seam.

**Disadvantages**:

- Requires the `ossf/scorecard-action` (and supporting actions) on the org
  Actions allow-list, plus provisioning the CI App key as a caller secret for
  full Branch-Protection scoring.

**Risk Assessment**:

- **Technical Risk**: Low. The App-token step is gated and `continue-on-error`,
  so a missing or failing key degrades the Branch-Protection score rather than
  failing the run; all actions are SHA-pinned.

## Decision

The org runs OpenSSF Scorecard as the central reusable workflow
`reusable-scorecard.yml`, invoked by each repository as a thin SHA-pinned
caller.

**Trigger model (caller-defined):** The reusable workflow itself is
`workflow_call` only; it documents the recommended caller triggers as
`branch_protection_rule`, a weekly `schedule`, and `push` to the default
branch. Posture is re-measured on the events that change it plus a periodic
baseline.

**Job and permissions:** The single job is `analysis` (`runs-on:
ubuntu-latest`). It requests `security-events: write` (upload SARIF),
`id-token: write` (publish to the OpenSSF API), `contents: read`, and
`actions: read`. The top-level workflow default permission is `contents: read`.

**Authentication:** Scorecard authenticates with the run's `GITHUB_TOKEN`
(`github.token`) by default. When the caller provides the `app-private-key`
secret and `vars.MIF_CI_CLIENT_APP_ID` is set, the workflow first mints an org
CI App installation token via
`actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1`
(v3.2.0), scoped to the calling repository, so Scorecard can read branch
protection (`administration:read`) and score the Branch-Protection heuristic
from real settings. That step is gated on the App-id variable (secrets cannot be
used in `if:`) and is `continue-on-error: true`; the Scorecard step's
`repo_token` resolves to `steps.app-token.outputs.token || github.token`, so a
missing or failed App token falls back to `GITHUB_TOKEN` (Branch-Protection then
limited). Publishing to the OpenSSF REST API is a public posture attestation and
requires the `id-token: write` OIDC permission.

**Scan and outputs:** Scorecard runs via
`ossf/scorecard-action@4eaacf0543bb3f2c246792bd56e8cdeffafb205a` (v2.4.3),
writing `scorecard.sarif` with `publish_results` driven by the
`publish-results` input (default `true`). The SARIF is uploaded to the
code-scanning hub under category `scorecard` via
`github/codeql-action/upload-sarif@8aad20d150bbac5944a9f9d289da16a4b0d87c1e`
(v4.36.2), and is also uploaded as the `scorecard-sarif` artifact (filename
`scorecard.sarif`, `if-no-files-found: error`) via
`actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` (v7.0.1) so
the attestation seam can sign it bound to a release subject. The workflow
exposes `sarif-artifact` (`scorecard-sarif`) and `sarif-filename`
(`scorecard.sarif`) as `workflow_call` outputs. Checkout uses
`actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0` (v7.0.0) with
`persist-credentials: false`.

This is Mode A consumption of the reusable quality-gate architecture (ADR-002):
each repo calls the org's reusable Scorecard gate rather than re-implementing
it.

## Consequences

### Positive

1. **Continuous, centralized posture measurement**: Posture is scored on
   default-branch push, branch-protection-rule change, and a weekly schedule
   from one audited implementation.
2. **Accurate Branch-Protection scoring with graceful degradation**: With the
   CI App key, the heuristic reflects real settings; without it, the run still
   completes on `GITHUB_TOKEN` at a reduced Branch-Protection score.
3. **Code-scanning and badge integration**: Findings land in the code-scanning
   hub as SARIF, and `publish-results: true` yields a public posture
   attestation and badge.
4. **Attestation-ready evidence**: The SARIF artifact feeds the signing seam
   (ADR-005), enabling a signed, release-bound posture attestation.

### Negative

1. **Allow-list and key provisioning**: `ossf/scorecard-action` and the
   supporting actions must be on the org Actions allow-list, and callers must
   provision the CI App key as a secret to get full Branch-Protection scoring.
2. **Public publication**: `publish-results: true` publishes posture to the
   OpenSSF API. This is intended for public repositories; it is a deliberate
   disclosure that callers must accept (the input can be overridden to
   `false`).

### Neutral

1. **SHA pin maintenance**: Callers pin `reusable-scorecard.yml` and it pins its
   own actions by full SHA. Updates require deliberate SHA bumps — the intended
   supply-chain posture (ADR-002), not a floating tag.
2. **Caller-owned triggers**: Because the reusable workflow is `workflow_call`,
   the trigger schedule lives in each caller; the reusable file only documents
   the recommended set.

## Decision Outcome

OpenSSF Scorecard runs org-wide as the `reusable-scorecard.yml` central
reusable workflow. The `analysis` job requests `security-events:write`,
`id-token:write`, `contents:read`, and `actions:read`; authenticates with the
run's `GITHUB_TOKEN` or an optional org CI App installation token for
Branch-Protection read; uploads SARIF to code-scanning and as an artifact; and
publishes results to the OpenSSF API by default. All `uses:` references are
pinned to full 40-character SHAs.

### Implementation

**Caller wiring (recommended triggers and permissions):**

```yaml
on:
  push:
    branches: [main]
  branch_protection_rule:
  schedule:
    - cron: '0 0 * * 1'   # weekly
  workflow_dispatch:

jobs:
  scorecard:
    permissions:
      security-events: write
      id-token: write
      contents: read
      actions: read
    uses: modeled-information-format/.github/.github/workflows/reusable-scorecard.yml@<sha>
    secrets:
      app-private-key: ${{ secrets.MIF_CI_CLIENT_APP_PRIVATE_KEY }}
```

**Required-status-check context** (format: `<caller-job-id> / <called-job-name>`):
`scorecard / analysis`.

**Reusable workflow file:** `.github/workflows/reusable-scorecard.yml`
(job `analysis`).

## Related Decisions

- [ADR-002: Reusable Quality-Gate Architecture](ADR-002-reusable-quality-gate-architecture.md) -- Scorecard is one of the central reusable gates; this ADR records its specific wiring under that architecture.
- [ADR-005: Signing, Attestation, and Verification](ADR-005-signing-attestation-verification.md) -- the `scorecard-sarif` artifact is the attestation seam this workflow exposes so the posture verdict can be signed and bound to a release subject.

## Links

- [OpenSSF Scorecard](https://github.com/ossf/scorecard) -- the posture-assessment tool and its 0-10 heuristics.
- [ossf/scorecard-action](https://github.com/ossf/scorecard-action) -- the GitHub Action wrapper run by this workflow.
- [SARIF specification](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html) -- the format uploaded to the code-scanning hub.
- [actions/create-github-app-token](https://github.com/actions/create-github-app-token) -- mints the org CI App installation token for Branch-Protection read.

## More Information

- **Date:** 2026-06-29
- **Source:** `.github/workflows/reusable-scorecard.yml`.
- **Related ADRs:** ADR-002, ADR-005

## Audit

### 2026-06-29

**Status:** Compliant

**Findings:**

| Finding | Files | Lines | Assessment |
|---------|-------|-------|------------|
| Workflow is `workflow_call` only; recommended caller triggers documented as `branch_protection_rule`, weekly `schedule`, and push to the default branch | `.github/workflows/reusable-scorecard.yml` | L9-L10, L24-L25 | compliant |
| `publish-results` input defaults to `true` (publish to OpenSSF API, public repos only) | `.github/workflows/reusable-scorecard.yml` | L26-L31 | compliant |
| Optional `app-private-key` secret enables Branch-Protection read via an App installation token (`administration:read`); omit to fall back to `GITHUB_TOKEN` | `.github/workflows/reusable-scorecard.yml` | L32-L41 | compliant |
| Workflow-call outputs `sarif-artifact` (`scorecard-sarif`) and `sarif-filename` (`scorecard.sarif`) expose the attestation seam | `.github/workflows/reusable-scorecard.yml` | L42-L48 | compliant |
| Top-level default permission is `contents: read` | `.github/workflows/reusable-scorecard.yml` | L50-L51 | compliant |
| Job is `analysis` with `security-events: write`, `id-token: write`, `contents: read`, `actions: read` | `.github/workflows/reusable-scorecard.yml` | L54-L61 | compliant |
| Checkout pinned with `persist-credentials: false` | `.github/workflows/reusable-scorecard.yml` | L63-L66 | compliant |
| CI App token minted via `actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1` (v3.2.0), gated on `vars.MIF_CI_CLIENT_APP_ID` and `continue-on-error: true` | `.github/workflows/reusable-scorecard.yml` | L73-L82 | compliant |
| Scorecard run via `ossf/scorecard-action@4eaacf0543bb3f2c246792bd56e8cdeffafb205a` (v2.4.3); `repo_token` resolves to App token or `github.token` | `.github/workflows/reusable-scorecard.yml` | L84-L91 | compliant |
| SARIF uploaded to code-scanning (category `scorecard`) via `github/codeql-action/upload-sarif@8aad20d150bbac5944a9f9d289da16a4b0d87c1e` (v4.36.2) | `.github/workflows/reusable-scorecard.yml` | L93-L97 | compliant |
| SARIF exposed as `scorecard-sarif` artifact (`if-no-files-found: error`) via `actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` (v7.0.1) | `.github/workflows/reusable-scorecard.yml` | L101-L107 | compliant |

**Summary:** Scorecard runs as the org's central reusable workflow. The
`analysis` job requests `security-events:write`, `id-token:write`,
`contents:read`, and `actions:read`; authenticates with the run's
`GITHUB_TOKEN` or an optional org CI App installation token for Branch-Protection
read; uploads SARIF to the code-scanning hub and as the `scorecard-sarif`
artifact; and publishes posture to the OpenSSF API by default. All `uses:`
references are pinned to full 40-character SHAs.

**Action Required:** None.
