---
title: "DAST and Load Testing (ZAP + k6), Opt-In Schedule/Dispatch-Driven"
description: "Dynamic analysis (OWASP ZAP) and load testing (Grafana k6) are provided as central reusable workflows that are opt-in and schedule/dispatch-driven rather than PR gates, because both require a live target the .github repo does not host; ZAP and k6 expose their JSON summaries as signable evidence for the attestation seam, and the in-repo dast.yml caller is manual-dispatch-only against a user-supplied URL."
type: adr
category: security
tags:
  - dast
  - zap
  - k6
  - load-testing
  - dynamic-analysis
  - security
status: accepted
created: 2026-06-29
updated: 2026-06-29
author: MIF Maintainers
project: modeled-information-format
technologies:
  - github-actions
  - owasp-zap
  - k6
  - sigstore
audience:
  - developers
  - architects
  - maintainers
related:
  - ADR-002-reusable-quality-gate-architecture.md
  - ADR-003-sast-gate-suite.md
  - ADR-007-scorecard-posture.md
---

# ADR-006: DAST and Load Testing (ZAP + k6), Opt-In Schedule/Dispatch-Driven

## Status

Accepted

## Context

### Background and Problem Statement

Static analysis, dependency auditing, and posture assessment cover a codebase at
rest, but two classes of defect surface only against a running system: web
application vulnerabilities exploitable over HTTP (the domain of dynamic
application security testing, DAST) and performance regressions under load. The
org's reusable quality-gate architecture (ADR-002) keeps gate logic central, so
DAST and load testing belong as org-level reusable workflows that any member
repo can call.

The structural difference from every other gate is the target. SAST, SCA, and
secret scanning run against source already present in the checkout. DAST and
load testing need a *live, reachable endpoint* — a deployed preview, a service
started in a prior job, or a public URL. A pull request does not, by itself,
produce such an endpoint. Wiring these as automatic push/PR gates would either
fail on every PR (no target) or require every repo to stand up an ephemeral
deployment for each PR, which is out of scope for the org defaults repo.

The `.github` org-defaults repo itself hosts no deployed application. It carries
the reusable workflows so member repos can consume them, plus a thin in-repo
caller for ZAP that exists only as a manually dispatched scaffold.

### Current Limitations Before This Decision

- No org-level reusable workflow existed for dynamic analysis or load testing;
  a repo wanting either had to assemble and pin the underlying actions itself.
- No evidence convention existed for binding a DAST or load-test verdict to a
  release subject through the org attestation seam.
- The org-defaults repo had no documented, supported way to run an ad-hoc DAST
  scan against an arbitrary URL without committing a scheduled job that would
  have no standing target to scan.

## Decision Drivers

### Primary Decision Drivers

1. **A live target is mandatory**: Both gates require a running endpoint, so
   neither can be an unconditional push/PR gate. The trigger model must be
   opt-in (schedule or manual dispatch by repos that have a target), not
   gate-on-every-change.
2. **Reuse over reinvention**: The underlying scanners (OWASP ZAP, Grafana k6)
   and their official actions are wrapped once, centrally, and consumed by
   member repos as SHA-pinned reusable workflows — consistent with ADR-002.
3. **Evidence is signable**: Each gate must emit a machine-readable verdict
   (JSON) that the org attestation seam can sign and bind to a release subject,
   so a dynamic or performance verdict can carry the same provenance guarantees
   as the rest of the suite.

### Secondary Decision Drivers

1. **Least privilege per gate**: ZAP needs only `contents: read` and must not
   open issues; k6 needs attestation write permissions only when it signs a
   summary. Each reusable workflow declares the minimum it needs.
2. **Fail-fast on misconfiguration**: An opt-in attestation path that is
   requested without the required subject inputs must fail loudly rather than
   silently skip and report success.
3. **SHA-pinned, fail-closed posture**: Every `uses:` reference is pinned to a
   full 40-character commit SHA; the org `pin-check` gate re-verifies this per
   repo. Third-party actions used here require an explicit org allow-list entry.

## Considered Options

### Option 1: Wire DAST/load as automatic push/PR gates

**Description**: Run ZAP and k6 on every push and pull request alongside the
static gates.

**Advantages**:

- Uniform trigger model with the rest of the quality-gate suite.

**Disadvantages**:

- There is no live target on a PR. The job would fail for lack of an endpoint,
  or each repo would have to stand up an ephemeral deployment per PR — neither
  is viable for an org-defaults repo with no deployed application.
- Active scanning and load generation are expensive and slow; running them on
  every change is wasteful for gates that cannot meaningfully evaluate most PRs.

**Risk Assessment**:

- **Technical Risk**: High. Guaranteed failures or large per-PR infrastructure
  cost; the gate would be disabled in practice.

### Option 2: Leave DAST and load testing to each repo

**Description**: Document the recommended scanners and let each member repo
assemble its own ZAP/k6 jobs.

**Advantages**:

- No central maintenance.

**Disadvantages**:

- Duplicated, divergent gate logic across repos; inconsistent action pins and
  permissions; no shared evidence convention for the attestation seam.
- Contradicts ADR-002's central-reusable model.

**Risk Assessment**:

- **Technical Risk**: Medium. Drift and inconsistent supply-chain posture
  across repos.

### Option 3: Central reusable ZAP + k6 workflows, opt-in and schedule/dispatch-driven (chosen)

**Description**: Provide `reusable-zap.yml` (OWASP ZAP full scan) and
`reusable-k6.yml` (Grafana k6 load test) as central reusable workflows. Both
are opt-in: a calling repo supplies the target (ZAP via a `target` URL input;
k6 via the target encoded in its script) and chooses when to run them
(typically a schedule or manual dispatch in the caller). Each exposes its JSON
summary as evidence the attestation seam can sign. The org-defaults repo ships a
thin `dast.yml` caller wired to `reusable-zap.yml`, dispatch-only against a
user-supplied URL because the repo hosts no standing target. No k6 caller ships
in this repo; `reusable-k6.yml` is consumed by member repos that have a system
under test.

**Advantages**:

- Matches the live-target constraint: opt-in, never an unconditional PR gate.
- Single, SHA-pinned implementation of each scanner, consumed org-wide.
- Both gates emit signable JSON evidence for release-bound attestation.
- Least-privilege permissions declared per reusable workflow.

**Disadvantages**:

- Requires org Actions allow-list entries for the third-party actions
  (`zaproxy/action-full-scan`, `grafana/setup-k6-action`,
  `grafana/run-k6-action`); these are not allow-listed by default.
- Dynamic and performance regressions are not caught on a PR; they surface only
  when the opt-in workflow runs against a live target.

**Risk Assessment**:

- **Technical Risk**: Low. Each component is independently auditable and
  SHA-pinned; the opt-in model avoids false failures while keeping the gates
  available to any repo with a target.

## Decision

DAST and load testing are provided as central reusable workflows that are
opt-in and schedule/dispatch-driven, not push/PR gates, because both require a
live target.

**`reusable-zap.yml` (OWASP ZAP full scan):** A `workflow_call` reusable
workflow. Inputs: `target` (required URL of the running target), `fail-action`
(boolean, default `true` — fail the job when ZAP reports alerts), and
`cmd-options` (default `-a`). It runs `zaproxy/action-full-scan` (spider +
active scan) with `allow_issue_writing: false`, keeping the job to
`contents: read` (it does not open GitHub issues). The ZAP JSON report
(`report_json.json`) is uploaded as the `dast-report` artifact with
`if: always()` — uploaded even on a failing scan — and exposed via the
`report-artifact` / `report-filename` outputs so the attestation seam
(`reusable-attest-scan.yml`) can sign the DAST verdict bound to a release
subject under predicate type
`https://modeled-information-format.github.io/attestations/dast/v1`.

**`reusable-k6.yml` (Grafana k6 load test):** A `workflow_call` reusable
workflow. The gate is k6's thresholds: on a threshold breach k6 exits 99
(`ThresholdsHaveFailed`), failing the job. Inputs: `script-path` (required),
`attest` (boolean, default `false`), and `subject-name` / `subject-digest`
(required only when `attest=true`). When `attest=true` it first validates that
both subject inputs are present and fails fast otherwise, then signs the k6 JSON
summary (`k6-summary.json`, written via `--summary-export`) with
`actions/attest` under predicate type
`https://modeled-information-format.github.io/attestations/k6-load/v1`. The job
holds `id-token: write`, `attestations: write`, and `contents: read`. The
caller is responsible for starting/targeting the system under test; the target
URL and thresholds live in the k6 script.

**`dast.yml` (in-repo caller):** A thin caller wired to
`./.github/workflows/reusable-zap.yml`. It triggers on `workflow_dispatch`
**only** — there is no `schedule:` trigger — because the org-defaults repo has
no deployed application and therefore no standing target. The operator supplies
a `target-url` input at dispatch time, which is passed through as the reusable
workflow's `target`. The caller passes only `target`, so `fail-action` takes
its default of `true`: a dispatched scan fails the job on alerts, while the
report is uploaded regardless. DAST is "not a hard PR failure" here in the
structural sense — it is never a push/PR gate — not because the job soft-fails.

No k6 caller is committed in this repo; `reusable-k6.yml` is consumed directly
by member repos that have a system under test.

This is the central-reusable consumption model of ADR-002 applied to the two
gates that need a live target.

## Consequences

### Positive

1. **Live-target gates without false failures**: ZAP and k6 run only when a
   repo opts in with a real target, so neither produces guaranteed PR failures
   for lack of an endpoint.
2. **Single SHA-pinned implementation**: Each scanner is wrapped once and
   consumed org-wide; action pins and permissions are maintained in one place.
3. **Signable dynamic/performance evidence**: Both gates emit JSON the
   attestation seam can sign and bind to a release subject, extending provenance
   to dynamic and performance verdicts.
4. **Ad-hoc DAST path**: `dast.yml` gives operators a supported way to scan an
   arbitrary URL on demand without committing a scheduled job that would have no
   target.

### Negative

1. **Allow-list additions**: `zaproxy/action-full-scan`,
   `grafana/setup-k6-action`, and `grafana/run-k6-action` must be added to the
   org Actions allow-list; they are not enabled by default.
2. **No PR-time coverage**: Dynamic and performance regressions are not caught
   on a pull request. They surface only when the opt-in workflow runs against a
   live target.

### Neutral

1. **Caller owns the target and cadence**: The reusable workflows do not stand
   up a target or impose a schedule. Each consuming repo decides when to run
   (schedule or dispatch) and how to provide the endpoint.
2. **k6 attestation is opt-in**: k6 signs a summary only when `attest=true` with
   valid subject inputs; otherwise it runs as a pass/fail threshold gate with no
   attestation. There is no standard performance predicate type, so a custom one
   is used.

## Decision Outcome

The org provides `reusable-zap.yml` and `reusable-k6.yml` as opt-in,
schedule/dispatch-driven reusable workflows for DAST and load testing. ZAP
emits a signable `report_json.json`; k6 gates on thresholds (exit 99 on breach)
and optionally signs `k6-summary.json`. The org-defaults repo ships a
dispatch-only `dast.yml` caller for ZAP against a user-supplied URL; no k6
caller ships here.

### Implementation

**Run an ad-hoc DAST scan (org-defaults repo):** dispatch `dast.yml` (Actions →
`dast` → Run workflow) and supply a `target-url`, e.g.
`https://staging.example.com`. The scan fails the run on ZAP alerts
(`fail-action` defaults to `true`); the `dast-report` artifact is produced
either way.

**Consume the reusables from a member repo (SHA-pinned):**

```yaml
jobs:
  gate-dast:
    permissions:
      contents: read
    uses: modeled-information-format/.github/.github/workflows/reusable-zap.yml@<sha>
    with:
      target: https://staging.example.com

  load:
    permissions:
      id-token: write
      attestations: write
      contents: read
    uses: modeled-information-format/.github/.github/workflows/reusable-k6.yml@<sha>
    with:
      script-path: tests/load.js
      attest: true
      subject-name: my-app
      subject-digest: ${{ needs.build.outputs.digest }}
```

**Pinned actions (full 40-char SHAs):** `zaproxy/action-full-scan@3c58388149901b9a03b7718852c5ba889646c27c` (v0.13.0),
`actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` (v7.0.1),
`actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0` (v7.0.0),
`grafana/setup-k6-action@db07bd9765aac508ef18982e52ab937fe633a065` (v1.2.1),
`grafana/run-k6-action@de51a7390bdf0ac85a3bef493691bd71d4c7c158` (v1.4.0),
`actions/attest@59d89421af93a897026c735860bf21b6eb4f7b26` (v4.1.0).

## Related Decisions

- [ADR-002: Reusable Quality-Gate Architecture](ADR-002-reusable-quality-gate-architecture.md) -- DAST and load testing are the live-target members of the central-reusable gate suite this ADR-002 establishes.
- [ADR-003: SAST Gate Suite](ADR-003-sast-gate-suite.md) -- the static counterpart; SAST runs at rest on every change, whereas DAST/k6 are opt-in because they need a running target.
- [ADR-007: Scorecard Posture](ADR-007-scorecard-posture.md) -- another scheduled/dispatch posture gate consumed via the reusable architecture.

## Links

- [OWASP ZAP](https://www.zaproxy.org/) -- the dynamic analysis scanner wrapped by `reusable-zap.yml`.
- [Grafana k6](https://k6.io/) -- the load/performance tool wrapped by `reusable-k6.yml`.
- [k6 thresholds](https://grafana.com/docs/k6/latest/using-k6/thresholds/) -- the pass/fail criteria whose breach exits k6 with code 99.

## More Information

- **Date:** 2026-06-29
- **Source:** `.github/workflows/reusable-zap.yml`, `.github/workflows/dast.yml`, `.github/workflows/reusable-k6.yml`.
- **Related ADRs:** ADR-002, ADR-003, ADR-007

## Audit

### 2026-06-29

**Status:** Compliant

**Findings:**

| Finding | Files | Lines | Assessment |
|---------|-------|-------|------------|
| `reusable-zap.yml` is a `workflow_call` reusable workflow; `target` is a required string input | `.github/workflows/reusable-zap.yml` | L32-L38 | compliant |
| ZAP `fail-action` input defaults to `true` (fail the job on alerts); `cmd-options` defaults to `-a` | `.github/workflows/reusable-zap.yml` | L39-L48 | compliant |
| ZAP exposes `report-artifact` (`dast-report`) and `report-filename` (`report_json.json`) outputs for the attestation seam | `.github/workflows/reusable-zap.yml` | L49-L55 | compliant |
| ZAP job runs `zaproxy/action-full-scan@3c58388149901b9a03b7718852c5ba889646c27c` (v0.13.0) with `allow_issue_writing: false`, kept to `contents: read` | `.github/workflows/reusable-zap.yml` | L57-L73 | compliant |
| ZAP JSON report uploaded via `actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` (v7.0.1) with `if: always()` | `.github/workflows/reusable-zap.yml` | L78-L84 | compliant |
| DAST verdict is signable under predicate type `https://modeled-information-format.github.io/attestations/dast/v1` (header convention) | `.github/workflows/reusable-zap.yml` | L15-L19 | compliant |
| `dast.yml` triggers on `workflow_dispatch` only — no `schedule:` trigger; requires a `target-url` input | `.github/workflows/dast.yml` | L11-L17 | compliant |
| `dast.yml` calls `./.github/workflows/reusable-zap.yml` passing only `target` (so `fail-action` defaults true) | `.github/workflows/dast.yml` | L22-L29 | compliant |
| `dast.yml` is a dispatch-only scaffold because the repo has no deployed/standing target | `.github/workflows/dast.yml` | L1-L8 | compliant |
| `reusable-k6.yml` is a `workflow_call` reusable workflow; `script-path` required, `attest` defaults false, `subject-name`/`subject-digest` default empty | `.github/workflows/reusable-k6.yml` | L27-L48 | compliant |
| k6 gate semantics: threshold breach exits 99 (`ThresholdsHaveFailed`), failing the job | `.github/workflows/reusable-k6.yml` | L3-L6 | compliant |
| k6 `load` job declares `id-token: write`, `attestations: write`, `contents: read`; pins `actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0` (v7.0.0) | `.github/workflows/reusable-k6.yml` | L53-L63 | compliant |
| k6 fails fast when `attest=true` without `subject-name`/`subject-digest` | `.github/workflows/reusable-k6.yml` | L67-L76 | compliant |
| k6 runs `grafana/setup-k6-action@db07bd9765aac508ef18982e52ab937fe633a065` (v1.2.1) and `grafana/run-k6-action@de51a7390bdf0ac85a3bef493691bd71d4c7c158` (v1.4.0) with `--summary-export=k6-summary.json` | `.github/workflows/reusable-k6.yml` | L78-L85 | compliant |
| k6 summary attested via `actions/attest@59d89421af93a897026c735860bf21b6eb4f7b26` (v4.1.0) under predicate type `https://modeled-information-format.github.io/attestations/k6-load/v1` | `.github/workflows/reusable-k6.yml` | L87-L93 | compliant |
| No k6 caller exists in this repo; `dast.yml` calls only `reusable-zap.yml` | `.github/workflows/dast.yml` | L27 | compliant |

**Summary:** DAST (OWASP ZAP) and load testing (Grafana k6) are provided as
central, SHA-pinned reusable workflows that are opt-in and
schedule/dispatch-driven rather than push/PR gates, because both require a live
target. ZAP exposes a signable `report_json.json` and runs without issue-writing
at `contents: read`; k6 gates on thresholds (exit 99 on breach) and optionally
signs `k6-summary.json` under a custom performance predicate type. The in-repo
`dast.yml` caller is dispatch-only against a user-supplied URL and passes only
`target`, so `fail-action` defaults to `true`. No k6 caller ships in this repo.

**Action Required:** None.
