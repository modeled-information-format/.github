---
title: "Reusable Attested Quality-Gate Architecture"
description: "The org centralizes all CI quality gates as reusable workflows in modeled-information-format/.github/.github/workflows/, consumed by every other repo as thin, SHA-pinned caller workflows; the Actions posture is fail-closed (every uses: is a full 40-char commit SHA, re-checked per-repo by the pin-check job, with actionlint validating workflow syntax). This is the umbrella architecture the gate ADRs (003-007) plug into."
type: adr
category: process
tags:
  - ci
  - reusable-workflows
  - supply-chain
  - sha-pinning
  - fail-closed
status: accepted
created: 2026-06-29
updated: 2026-06-29
author: MIF Maintainers
project: modeled-information-format
technologies:
  - github-actions
  - actionlint
  - reusable-workflows
audience:
  - developers
  - architects
  - maintainers
related:
  - ADR-001-org-label-sync.md
  - ADR-003-sast-gate-suite.md
  - ADR-004-supply-chain-scanning.md
  - ADR-005-signing-attestation-verification.md
  - ADR-006-dast-and-load-testing.md
  - ADR-007-scorecard-posture.md
  - ADR-008-github-app-ci-identity.md
  - ADR-009-branch-protection-standardization.md
  - ADR-010-plugin-catalog-hub.md
---

# ADR-002: Reusable Attested Quality-Gate Architecture

## Status

Accepted

## Context

### Background and Problem Statement

The `modeled-information-format` org maintains several repositories — the MIF
spec, docs sites, plugins, and templates — that each need the same CI quality
gates: workflow-syntax linting, static analysis, dependency and secret scanning,
infrastructure-as-code policy, posture assessment, dynamic analysis, and
artifact signing and attestation. If each repo implemented these gates
independently, the org would maintain N parallel copies of the same logic, each
free to drift, each a separate place a supply-chain regression could enter.

GitHub Actions is itself a supply-chain surface. A mutable tag reference
(`@v4`, `@main`) resolves to whatever commit the action's owner last pushed to
that tag; a compromised or repointed tag silently changes what runs in CI. The
`tj-actions`/`trivy-action`-class ecosystem compromises demonstrated that this
is not theoretical. The org therefore needs a single, enforced policy: every
Action reference is pinned to a full 40-character commit SHA, and that pin is
re-checked mechanically rather than trusted.

This ADR records the umbrella decision already in production: gate logic lives
once, centrally, as reusable workflows in
`modeled-information-format/.github/.github/workflows/`; every other repo
consumes those gates as thin caller workflows pinned by commit SHA; and the
posture is fail-closed, enforced per-repo by a `pin-check` job and validated for
syntax by `actionlint`. The individual gate suites (SAST, supply-chain scanning,
signing/attestation, DAST/load, posture) are recorded in ADR-003 through
ADR-007; this ADR is the architecture they plug into.

### Current Limitations Before This Decision

- No central home for gate logic: each repo would carry its own copy of every
  scanner invocation, with no mechanism to keep them aligned.
- No enforced pinning posture: nothing prevented a workflow from referencing an
  Action by mutable tag, leaving every consuming repo exposed to a repointed
  tag.
- No mechanical re-check: even with a pinning convention, a drifted or
  hand-edited workflow could reintroduce an unpinned reference unnoticed.
- No org-level syntax gate: malformed workflow YAML would fail only at runtime,
  per repo, rather than being caught by a shared linter.

## Decision Drivers

### Primary Decision Drivers

1. **Single source of gate logic**: A gate must be implemented and maintained in
   exactly one place. Consuming repos call it; they do not re-implement it. A fix
   or upgrade to a gate happens once and propagates by SHA bump.
2. **Fail-closed SHA-pinning**: Every `uses:` reference to an external Action or
   cross-repo reusable workflow must be a full 40-character commit SHA. Mutable
   tags and floating refs are rejected. This is enforced, not advised.
3. **Per-repo mechanical re-check**: Pinning is verified by a job that fails the
   run on the first unpinned reference, so the posture holds independently in
   every repo regardless of how a workflow was authored or edited.

### Secondary Decision Drivers

1. **Thin callers**: A consuming repo's workflow should be a minimal caller —
   job declaration, least-privilege permissions, and a SHA-pinned `uses:` — with
   all substance in the reusable. This keeps the consumer surface small and
   auditable.
2. **Syntax validation as a shared gate**: Workflow YAML should be linted by a
   single, verified `actionlint` reusable rather than re-tooled per repo.
3. **Verified fetch where no pinned Action exists**: When a tool has no
   allow-listed, SHA-pinnable Action (e.g. actionlint itself), the reusable
   performs a checksum-verified, fail-closed download once, centrally, rather
   than letting each caller hand-roll an unverified fetch.

## Considered Options

### Option 1: Per-repo copied workflows (status quo to avoid)

**Description**: Each repo carries its own full copy of every gate workflow,
edited in place.

**Advantages**:

- No cross-repo dependency; each repo is self-contained.

**Disadvantages**:

- N parallel copies drift independently; a fix must be applied N times.
- No single enforcement point for pinning; each copy can reintroduce a mutable
  tag.
- Review burden multiplies: every gate change is reviewed once per repo.

**Risk Assessment**:

- **Technical Risk**: High. Drift and inconsistent posture across repos; a
  supply-chain regression can enter any single copy unnoticed.

### Option 2: Central reusables consumed by floating tag

**Description**: Centralize gate logic as reusable workflows, but let callers
reference them by a mutable tag (`@v1`, `@main`) for convenience.

**Advantages**:

- Single gate implementation; callers auto-receive updates without a SHA bump.

**Disadvantages**:

- A mutable tag is exactly the supply-chain risk this architecture exists to
  remove. A repointed tag silently changes what every caller runs.
- Defeats the fail-closed posture: `pin-check` exists specifically to reject
  non-SHA references.

**Risk Assessment**:

- **Technical Risk**: High. Reintroduces the mutable-reference attack surface at
  the reusable layer.

### Option 3: Central reusables consumed as thin SHA-pinned callers (chosen)

**Description**: Implement every gate once as a reusable workflow in
`modeled-information-format/.github/.github/workflows/`. Every other repo
consumes each gate as a thin caller whose `uses:` references the reusable by full
40-character commit SHA. A `pin-check` reusable re-checks the posture per repo
and fails on the first unpinned reference; an `actionlint` reusable validates
workflow syntax. Where a tool has no pinnable Action, the reusable performs a
checksum-verified fail-closed download internally.

**Advantages**:

- Gate logic lives once; upgrades propagate by a deliberate SHA bump.
- Fail-closed: unpinned references are rejected mechanically, per repo.
- Thin callers keep the consumer surface minimal and auditable.
- Same-repo reusable calls use local `./` paths (exempt from pinning), so the
  central repo dogfoods its own gates without redundant self-pins.

**Disadvantages**:

- Callers must update the pinned SHA when a reusable changes; updates are not
  automatic. This is the intended trade-off (pinning over floating tags).
- Composite third-party actions that hide tag-pinned nested actions cannot be
  used directly; such steps must be inlined with SHA-pinned actions.

**Risk Assessment**:

- **Technical Risk**: Low. Each reusable is independently auditable; the
  fail-closed `pin-check` prevents an unpinned reference from surviving in any
  consuming repo.

## Decision

The org centralizes all CI quality gates as reusable workflows in
`modeled-information-format/.github/.github/workflows/`. Every other repo
consumes each gate as a **thin, SHA-pinned caller workflow**. The Actions posture
is **fail-closed**: every external `uses:` reference is a full 40-character commit
SHA, re-checked per repo by the `pin-check` job, with `actionlint` validating
workflow syntax.

**Central reusables.** Each gate is a `reusable-*.yml` workflow exposing a
`workflow_call` interface with typed inputs and least-privilege `permissions`.
The set includes `reusable-actionlint`, `reusable-sast-codeql`,
`reusable-semgrep`, `reusable-sca-osv`, `reusable-trivy`, `reusable-checkov`,
`reusable-secrets`, `reusable-shellcheck`, `reusable-scorecard`, `reusable-zap`,
`reusable-k6`, `reusable-cosign-sign`, `reusable-attest-scan`,
`reusable-verify-gates`, and `reusable-vex`, plus the `pin-check` enforcement
workflow. The individual gate suites are detailed in ADR-003 (SAST), ADR-004
(supply-chain scanning), ADR-005 (signing/attestation/verification), ADR-006
(DAST and load testing), and ADR-007 (Scorecard posture).

**Thin callers.** A consuming repo wires a gate as a minimal job: a name,
least-privilege `permissions`, and a `uses:` referencing the reusable by full
commit SHA — for example, the `actionlint` caller in this repo's `ci.yml`:

```yaml
jobs:
  actionlint:
    name: actionlint
    permissions:
      contents: read
    uses: modeled-information-format/.github/.github/workflows/reusable-actionlint.yml@e5f42faca6bc9f9a2bc62ddbca9340445771cf66
```

Same-repo callers (the central repo dogfooding its own gates) reference reusables
by local `./.github/workflows/...` path, which is exempt from SHA-pinning and
`pin-check`; cross-repo callers always pin by commit SHA.

**Fail-closed pinning (`pin-check`).** The `pin-check` reusable scans a directory
(default `.github`) for every `uses: owner/repo...@ref` reference, isolates the
ref token, and asserts it matches `^[0-9a-f]{40}$`. Local reusable-workflow calls
(`./...`) and digest-pinned container actions (`docker://...@sha256:`) are
exempt. The run fails on the first reference that is not a 40-character SHA. It
runs with top-level `permissions: {}` and a `contents: read` job scope.

**Syntax validation (`actionlint`).** The `reusable-actionlint` workflow installs
`actionlint` via a pinned, checksum-verified download (`sha256sum -c` against a
pinned digest under `set -euo pipefail`, fail-closed) because no allow-listed
pinned Action exists for it, then lints the workflow files. Version and sha256
are overridable together; a new digest is resolved from the release's published
checksums, never from memory.

**Org Actions settings.** The posture is backed by org-level settings: allow
GitHub-created and Marketplace-verified actions, allow an explicit third-party
allow-list, and **require actions to be pinned to a full-length commit SHA**.
Same-org (`modeled-information-format/*`) and GitHub-created (`actions/*`,
`github/*`) actions are always allowed; every other publisher must be added to
the allow-list before a gate referencing it can run.

## Consequences

### Positive

1. **One implementation per gate**: A gate is fixed or upgraded once and
   propagates to all consumers by SHA bump. No parallel copies to keep aligned.
2. **Enforced fail-closed posture**: Unpinned references are rejected
   mechanically by `pin-check` in every repo, independent of author discipline.
3. **Small auditable consumer surface**: Thin callers contain only a job name,
   least-privilege permissions, and a pinned `uses:` — easy to review.
4. **Verified fetch for un-pinnable tools**: Tools without a pinnable Action
   (actionlint) are fetched once with a checksum-verified, fail-closed download
   in the reusable, not re-rolled per caller.

### Negative

1. **Manual SHA bumps**: When a reusable changes, every consuming caller must
   update the pinned SHA. Updates are deliberate, not automatic — the intended
   trade-off for rejecting floating tags.
2. **No hidden composite actions**: Composite third-party actions that nest
   tag-pinned actions cannot be used directly; such steps must be inlined with
   SHA-pinned actions, adding caller verbosity.

### Neutral

1. **Allow-list maintenance**: Adding a gate that introduces a new third-party
   action requires an org allow-list entry before that gate can run; otherwise
   the workflow startup-fails. This is org policy working as designed.
2. **Two reference styles coexist**: Cross-repo callers pin by SHA; same-repo
   callers in the central repo use local `./` paths. Both are intentional and
   distinguished by `pin-check`'s exemption rules.

## Decision Outcome

All org CI quality gates are implemented once as reusable workflows in
`modeled-information-format/.github/.github/workflows/` and consumed by other
repos as thin, SHA-pinned callers. The posture is fail-closed: every external
`uses:` is a full 40-character commit SHA, re-checked per repo by `pin-check`,
with `actionlint` validating workflow syntax. ADR-003 through ADR-007 record the
individual gate suites that plug into this architecture.

### Implementation

**Consume a gate (thin caller, cross-repo):**

```yaml
jobs:
  actionlint:
    name: actionlint
    permissions:
      contents: read
    uses: modeled-information-format/.github/.github/workflows/reusable-actionlint.yml@<full-40-char-sha>
```

**Enforce pinning per repo (caller for `pin-check`):**

```yaml
jobs:
  pin-check:
    permissions:
      contents: read
    uses: modeled-information-format/.github/.github/workflows/pin-check.yml@<full-40-char-sha>
    # optional input: scan-dir (default ".github")
```

**Required-status-check contexts** (format: `<caller-job-id> / <called-job-name>`):
`actionlint / actionlint`, `pin-check / pin-check`.

**Pinning rule enforced by `pin-check`:** every `uses: owner/repo...@ref` ref must
match `^[0-9a-f]{40}$`; `./...` (local reusable) and `docker://...@sha256:`
(digest-pinned container) are exempt; the run fails on the first violation.

## Related Decisions

- [ADR-003: SAST Gate Suite](ADR-003-sast-gate-suite.md) -- the CodeQL/Semgrep static-analysis reusables consumed under this architecture.
- [ADR-004: Supply-Chain Scanning](ADR-004-supply-chain-scanning.md) -- the SCA, secrets, IaC, and license-scanning reusables that plug into these thin callers.
- [ADR-005: Signing, Attestation, and Verification](ADR-005-signing-attestation-verification.md) -- the signing/attest/verify reusables consumed as SHA-pinned callers.
- [ADR-006: DAST and Load Testing](ADR-006-dast-and-load-testing.md) -- the ZAP and k6 reusables, opt-in callers under the same pinning posture.
- [ADR-007: Scorecard Posture](ADR-007-scorecard-posture.md) -- the OpenSSF Scorecard reusable, consumed as a thin SHA-pinned caller.

## Links

- [Security hardening for GitHub Actions — pin actions to a full-length commit SHA](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions#using-third-party-actions) -- the primary source cited by `pin-check.yml` for the SHA-pinning posture.
- [Reusing workflows (GitHub Actions)](https://docs.github.com/en/actions/using-workflows/reusing-workflows) -- the `workflow_call` mechanism the central reusables expose.
- [rhysd/actionlint](https://github.com/rhysd/actionlint) -- the workflow-syntax linter fetched (checksum-verified) by `reusable-actionlint.yml`.

## More Information

- **Date:** 2026-06-29
- **Source:** `README.md` (GitHub Actions policy), `.github/workflows/pin-check.yml`, `.github/workflows/reusable-actionlint.yml`, `.github/workflows/ci.yml`, `.github/workflows/sast.yml`.
- **Related ADRs:** ADR-003, ADR-004, ADR-005, ADR-006, ADR-007

## Audit

### 2026-06-29

**Status:** Compliant

**Findings:**

| Finding | Files | Lines | Assessment |
|---------|-------|-------|------------|
| Org posture is fail-closed and SHA-pinned: GitHub Actions policy requires actions pinned to a full-length commit SHA, "never disable", re-checked per-repo by `pin-check` | `README.md` | L8-L19 | compliant |
| Same-org (`modeled-information-format/*`) and GitHub-created (`actions/*`, `github/*`) actions always allowed; all other publishers require an allow-list entry | `README.md` | L21-L23 | compliant |
| `pin-check` is a `workflow_call` reusable scanning a directory (default `.github`) for unpinned `uses:` references | `.github/workflows/pin-check.yml` | L17-L24, L36-L60 | compliant |
| `pin-check` asserts each ref matches `^[0-9a-f]{40}$`; fails on first violation (`rc=1`, `exit "$rc"`) | `.github/workflows/pin-check.yml` | L56-L64 | compliant |
| `pin-check` exempts local reusable calls (`./*`) and digest-pinned container actions (`docker://*@sha256:*`) | `.github/workflows/pin-check.yml` | L51-L54 | compliant |
| `pin-check` runs least-privilege: top-level `permissions: {}`, job scope `contents: read` | `.github/workflows/pin-check.yml` | L26, L31-L32 | compliant |
| `pin-check` checkout itself pinned to a 40-char SHA (`actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0`, v7.0.0) | `.github/workflows/pin-check.yml` | L35 | compliant |
| `reusable-actionlint` is a `workflow_call` reusable that installs actionlint via a pinned, checksum-verified, fail-closed download (`sha256sum -c -` under `set -euo pipefail`) | `.github/workflows/reusable-actionlint.yml` | L26-L43, L57-L74 | compliant |
| `reusable-actionlint` documents the verified-fetch rationale (no allow-listed pinned Action for actionlint) and resolving digests from published checksums, never from memory | `.github/workflows/reusable-actionlint.yml` | L1-L15 | compliant |
| Thin caller pins the reusable by full 40-char SHA: `reusable-actionlint.yml@e5f42faca6bc9f9a2bc62ddbca9340445771cf66` | `.github/workflows/ci.yml` | L16 | compliant |
| Thin caller declares least-privilege `permissions: contents: read` at workflow and job level | `.github/workflows/ci.yml` | L8-L9, L14-L15 | compliant |
| Same-repo callers reference reusables by local `./` path (exempt from SHA-pinning and `pin-check`), dogfooding the central gates | `.github/workflows/sast.yml` | L8-L11, L34, L44 | compliant |

**Summary:** Gate logic is centralized as `reusable-*.yml` workflows exposing
`workflow_call` interfaces in `modeled-information-format/.github`. Other repos
consume each gate as a thin caller pinned by full 40-character commit SHA;
same-repo callers use exempt local `./` paths. The fail-closed posture is
enforced org-wide by the "require full-length SHA" setting and re-checked per
repo by `pin-check`, which rejects any non-SHA reference. `reusable-actionlint`
validates workflow syntax with a checksum-verified, fail-closed download. This is
the umbrella architecture the gate ADRs (003-007) plug into.

**Action Required:** None.
