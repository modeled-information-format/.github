---
title: "Supply-Chain Scanning (OSV, Secrets, Trivy, Checkov, VEX)"
description: "The org's supply-chain scanning layer is delivered as five SHA-pinned reusable workflows — dependency vulnerabilities (OSV-Scanner + dependency-review), secret scanning (Gitleaks + TruffleHog), IaC/license scanning (Trivy), IaC policy-as-code (Checkov), and OpenVEX exploitability disposition. Most gates normalize on SARIF and the code-scanning required check is the merge gate; the hard-fail exceptions are verified live secrets, Trivy image vulnerabilities, and the dependency-review PR gate."
type: adr
category: security
tags:
  - sca
  - osv
  - secrets
  - trivy
  - checkov
  - vex
  - supply-chain
  - security
status: accepted
created: 2026-06-29
updated: 2026-06-29
author: MIF Maintainers
project: modeled-information-format
technologies:
  - github-actions
  - osv-scanner
  - gitleaks
  - trufflehog
  - trivy
  - checkov
  - openvex
audience:
  - developers
  - architects
  - maintainers
related:
  - ADR-002-reusable-quality-gate-architecture.md
  - ADR-003-sast-gate-suite.md
  - ADR-005-signing-attestation-verification.md
---

# ADR-004: Supply-Chain Scanning (OSV, Secrets, Trivy, Checkov, VEX)

## Status

Accepted

## Context

### Background and Problem Statement

The `modeled-information-format` org publishes a normative specification, JSON
Schemas, and several runnable artifacts (a Python plugin, a VS Code extension, a
composite GitHub Action). Each consumes third-party dependencies, ships hook
scripts and configuration, and is built by GitHub Actions workflows. The supply
chain therefore has several distinct attack surfaces: a vulnerable transitive
dependency, a leaked credential in a script or fixture, a misconfigured
infrastructure-as-code file, and a malicious or compromised Action pinned by a
mutable tag.

A single scanner does not cover these surfaces, and the surfaces are not
redundant: dependency vulnerability databases, secret detectors, and IaC policy
engines look for fundamentally different defects. The org needed each scanning
concern available to every repo as a reusable, centrally maintained gate rather
than re-implemented per repo. This ADR records the decision to deliver the
supply-chain scanning layer as a set of SHA-pinned reusable workflows in the
`modeled-information-format/.github` repo (the reusable quality-gate
architecture of ADR-002), and the per-gate fail posture each one adopts.

Static application security testing (CodeQL, Semgrep) is a separate concern
recorded in ADR-003 and is out of scope here. Signing, attestation, and
verification mechanics are recorded in ADR-005; this ADR references that seam
where the VEX gate attaches a signed disposition to an artifact digest.

### Current Limitations Before This Decision

- No org-wide dependency vulnerability scan beyond repo-level Dependabot
  alerts; no independent second opinion against the OSV database and no PR
  merge gate that blocks a newly introduced vulnerable dependency or
  disallowed license.
- No secret scanning over hook scripts, fixtures, and bundled plugin/MCP
  source; a committed live credential would go undetected.
- No infrastructure-as-code misconfiguration, license, or policy-as-code
  scanning.
- No mechanism to disposition known-but-not-exploitable findings, so a clean
  scan was effectively required to be zero findings — an unsustainable bar.

## Decision Drivers

### Primary Decision Drivers

1. **Defense in depth across distinct surfaces**: Dependency, secret, IaC, and
   policy defects are different classes of defect. Each needs a purpose-built
   scanner; one all-in-one tool would cover none of them well.
2. **Right fail posture per gate**: A verified live secret must fail the build
   immediately; an unconfirmed advisory IaC misconfiguration should surface in
   the code-scanning hub for triage, not block every PR. The fail posture must
   match the certainty and severity of each finding class, not a blanket
   policy.
3. **Supply-chain correctness of the gates themselves**: Every Action `uses:`
   reference must be pinned to a full 40-character commit SHA. Scanning actions
   are themselves a supply-chain risk (see the Trivy CVE-2026-33634 note
   below); the gate layer must hold itself to the standard it enforces.

### Secondary Decision Drivers

1. **Minimize the org Actions allow-list**: Each third-party Action added to
   the org "Allow select actions" policy is a one-time review cost and an
   ongoing trust dependency. Gates that can install their tooling as
   checksum-verified binaries (or via pip / `go install`) avoid an allow-list
   entry entirely.
2. **Findings must be actionable, not just reported**: A code-scanning hub full
   of undispositioned advisories is noise. An OpenVEX document records
   per-vulnerability exploitability status so the deploy gate can enforce "no
   undispositioned high/critical vulnerabilities" rather than "zero findings".
3. **Reuse over reinvention**: Centralizing each gate as a reusable workflow
   keeps scanning logic in one place; callers wire to it by SHA pin.

## Considered Options

### Option 1: GitHub-native scanning only (status quo)

**Description**: Rely on repo-level Dependabot alerts and GitHub secret
scanning, with no additional OSV, IaC, license, policy, or VEX layer.

**Advantages**:

- Zero workflow authoring; enabled at the repo settings level.

**Disadvantages**:

- No independent second opinion against the OSV database and no PR merge gate
  that fails on a newly introduced vulnerable dependency or disallowed license.
- No IaC misconfiguration, license, or policy-as-code coverage.
- No exploitability disposition layer; advisories cannot be triaged to a
  defensible "no undispositioned high/critical" gate.

**Risk Assessment**:

- **Technical Risk**: High. Whole classes of supply-chain defect (IaC,
  license, secrets in scripts) are unscanned.

### Option 2: A single all-in-one scanner

**Description**: Adopt one vendor scanner configured to cover dependencies,
secrets, and IaC together.

**Advantages**:

- One tool to configure and pin.

**Disadvantages**:

- Couples unrelated concerns; a single tool's dependency database, secret
  detectors, and IaC policy catalog are each weaker than the purpose-built
  best-in-class tool. Gitleaks and TruffleHog, for example, produce largely
  non-overlapping true positives — collapsing them into one engine loses
  coverage.
- A single fail posture cannot fit all finding classes (verified secrets vs
  advisory misconfigurations).

**Risk Assessment**:

- **Technical Risk**: Medium. Broad but shallow; one engine becomes a single
  point of both coverage gaps and trust.

### Option 3: Per-gate SHA-pinned reusable workflows, soft-fail to code-scanning + VEX disposition (chosen)

**Description**: Deliver each scanning concern as its own reusable workflow in
`modeled-information-format/.github`: `reusable-sca-osv.yml` (OSV-Scanner +
dependency-review), `reusable-secrets.yml` (Gitleaks + TruffleHog),
`reusable-trivy.yml` (IaC misconfiguration + license, optional image scan),
`reusable-checkov.yml` (IaC policy-as-code), and `reusable-vex.yml` (OpenVEX
disposition). Most scanners normalize on SARIF and upload to the code-scanning
hub, where the "Code scanning results" required check is the merge gate; the
hard-fail exceptions are reserved for high-certainty findings. The VEX layer
attaches a signed exploitability disposition to the artifact digest so advisory
findings become triageable rather than blocking.

**Advantages**:

- Best-in-class tool per surface; non-redundant coverage (e.g. Gitleaks +
  TruffleHog, Trivy + Checkov on IaC).
- Fail posture is set per gate to match finding certainty and severity.
- Three of the five gates (secrets, Checkov, VEX) install tooling as
  checksum-verified binaries / pip / `go install` and add nothing to the org
  Actions allow-list.
- Each gate is centrally maintained; callers pin by SHA.

**Disadvantages**:

- Two gates (OSV, Trivy) reference third-party Actions that must be on the org
  allow-list.
- Five workflows to maintain and pin rather than one.

**Risk Assessment**:

- **Technical Risk**: Low. Each gate is independently auditable; SHA pinning
  and checksum-verified binaries bound the trust surface; the code-scanning
  required check plus targeted hard-fails provide the merge gate.

## Decision

The org adopts the supply-chain scanning layer as five SHA-pinned reusable
workflows. Every Action `uses:` reference is pinned to a full 40-character
commit SHA; tool binaries are version-pinned and checksum-verified. The
per-gate fail posture is as follows.

**`reusable-sca-osv.yml` (`sca-osv`)** — two complementary dependency layers
(Dependabot alerts are the third, configured at the repo level outside this
workflow):

- Job `osv-scanner` runs Google's OSV-Scanner inline via
  `google/osv-scanner-action/osv-scanner-action` and `…/osv-reporter-action`
  (both `fa4ff678dd5d0a4fa3d628e57af8162873e93cd6`, v2.3.8), producing JSON →
  SARIF and uploading to the code-scanning hub. The scan step is
  `continue-on-error: true` — an independent second opinion against the OSV
  database, reported as a soft finding.
- Job `dependency-review` runs `actions/dependency-review-action`
  (`a1d282b36b6f3519aa1f3fc636f609c47dddb294`, v5.0.0) only on
  `pull_request`; it is a **hard PR gate** that fails when a PR introduces a
  vulnerable dependency or disallowed license at or above `fail-on-severity`
  (default `high`).

**`reusable-secrets.yml` (`secrets`)** — Gitleaks and TruffleHog run over the
scan directory because they produce largely non-overlapping true positives.
Both install as checksum-verified release binaries (Gitleaks `8.30.1`,
TruffleHog `3.95.6`) — no third-party Action, no allow-list entry.

- Gitleaks runs with `--exit-code 0` (soft-fail): findings normalize on SARIF
  and upload to the code-scanning hub (the gate).
- TruffleHog runs in `--results=verified` mode and **hard-fails the job** when
  it confirms one or more verified live secrets (`fail-on-verified`, default
  `true`). A verified credential is not advisory.

**`reusable-trivy.yml` (`trivy`)** — Trivy adds IaC misconfiguration, license,
and optional image scanning via `aquasecurity/trivy-action`
(`ed142fd0673e97e23eac54620cfb913e5ce36c25`, v0.36.0). The header records
CVE-2026-33634 (March 2026: 76 of 77 trivy-action tags force-pushed to
credential-stealing malware) as the reason the SHA pin must never be replaced
with a tag.

- Job `iac-license` scans the filesystem with `scanners: misconfig,license` at
  `exit-code: '0'` (soft-fail) — findings go to the code-scanning hub.
- Job `image` runs only when `image-ref` is set, scanning by digest at
  `exit-code: '1'` — **fail-closed** on image vulnerabilities at or above
  `severity` (default `HIGH,CRITICAL`).

**`reusable-checkov.yml` (`checkov`)** — Checkov adds a graph/dataflow
policy-as-code engine with a distinct policy catalog, deliberately
non-redundant with Trivy's rule-based IaC scan (separate SARIF categories,
separate attestation predicates: `iac-misconfig` vs `iac-policy`). Checkov is
installed from PyPI at an exact pinned version (`3.2.524`) into an isolated
virtualenv — no third-party Action, no allow-list entry. The `iac-policy` job
runs `--soft-fail`: findings normalize on SARIF and the code-scanning required
check is the merge gate. The default `framework` is `terraform`, configurable
by the caller.

**`reusable-vex.yml` (`vex`)** — Not a scanner but a disposition layer. A clean
scan is rarely zero findings; an OpenVEX document maintained in the repo records
per-vulnerability status (`not_affected` / `affected` / `fixed` /
`under_investigation`) so the deploy gate can enforce "no undispositioned
high/critical vulnerabilities". The `attest-vex` job normalizes the document
with `vexctl merge` (vexctl `v0.4.1` via `go install`, immutable through the Go
checksum database) and attests it bound to the artifact digest via
`actions/attest` (`59d89421af93a897026c735860bf21b6eb4f7b26`, v4.1.0) with
predicate type `https://openvex.dev/ns/v0.2.0`. The attestation seam itself is
recorded in ADR-005.

The architectural invariant: most gates normalize on SARIF and the
code-scanning "Code scanning results" required check is the merge gate; the
hard-fail exceptions are verified live secrets (TruffleHog), Trivy image
vulnerabilities, and the dependency-review PR gate. VEX makes the soft-fail
output actionable by recording exploitability disposition.

## Consequences

### Positive

1. **Non-redundant coverage across surfaces**: Dependencies (OSV +
   dependency-review), secrets (Gitleaks + TruffleHog), IaC (Trivy + Checkov),
   and exploitability disposition (VEX) each get a purpose-built layer.
2. **Fail posture matches finding certainty**: Verified secrets and image
   vulnerabilities fail the build; advisory IaC findings surface in the
   code-scanning hub for triage; the dependency-review gate blocks bad PRs.
3. **Minimal allow-list footprint**: Three of five gates (secrets, Checkov,
   VEX) install tooling as checksum-verified binaries / pip / `go install` and
   add nothing to the org Actions allow-list.
4. **Actionable findings**: The OpenVEX layer turns "zero findings" into "no
   undispositioned high/critical", a defensible and maintainable bar.

### Negative

1. **Allow-list additions**: `google/osv-scanner-action` and
   `aquasecurity/trivy-action` must be on the org Actions allow-list, each a
   one-time review and an ongoing trust dependency.
2. **Five workflows to maintain and pin**: Callers pin five reusable workflows
   by SHA; a reusable-workflow change requires updating callers' pins.

### Neutral

1. **Tool versions are pinned and must be bumped deliberately**: Gitleaks,
   TruffleHog, Checkov, and vexctl are version-pinned (and checksum/Go-checksum
   verified). Updating them is an explicit step, which is the correct
   supply-chain posture but is not automatic.
2. **VEX requires a maintained document**: The exploitability gate only works
   if `.vex/openvex.json` is kept current; the `attest-vex` job fails if the
   document is absent.

## Decision Outcome

Each repo wires the supply-chain gates it needs by calling the reusable
workflows at a pinned org SHA. Dependency, secret, IaC misconfiguration,
license, and policy findings normalize on SARIF and land in the code-scanning
hub, where the required check is the merge gate; verified secrets, Trivy image
vulnerabilities, and the dependency-review PR gate hard-fail. The VEX gate
attaches a signed exploitability disposition to the artifact digest.

### Implementation

**Reusable workflow paths** (in `modeled-information-format/.github`):

- `.github/workflows/reusable-sca-osv.yml` — jobs `osv-scanner`,
  `dependency-review`.
- `.github/workflows/reusable-secrets.yml` — job `secrets`.
- `.github/workflows/reusable-trivy.yml` — jobs `iac-license`, `image`.
- `.github/workflows/reusable-checkov.yml` — job `iac-policy`.
- `.github/workflows/reusable-vex.yml` — job `attest-vex`.

**Caller wiring (example):**

```yaml
jobs:
  sca:
    permissions:
      actions: read
      contents: read
      security-events: write
      pull-requests: write
    uses: modeled-information-format/.github/.github/workflows/reusable-sca-osv.yml@<sha>
    with:
      fail-on-severity: high
  secrets:
    permissions:
      contents: read
      security-events: write
      actions: read
    uses: modeled-information-format/.github/.github/workflows/reusable-secrets.yml@<sha>
  trivy:
    permissions:
      contents: read
      security-events: write
      actions: read
    uses: modeled-information-format/.github/.github/workflows/reusable-trivy.yml@<sha>
  checkov:
    permissions:
      contents: read
      security-events: write
      actions: read
    uses: modeled-information-format/.github/.github/workflows/reusable-checkov.yml@<sha>
```

The required-status-check context string a caller registers is
`<caller-job-id> / <reusable-job-name>` (e.g. `sca / osv-scanner`,
`sca / dependency-review`, `secrets / secrets`, `trivy / iac-license`,
`checkov / iac-policy`); the `caller-job-id` is chosen by each calling
workflow and is not fixed by the reusable workflows.

## Related Decisions

- [ADR-002: Reusable Quality-Gate Architecture](ADR-002-reusable-quality-gate-architecture.md) -- these five scanning workflows are instances of the reusable quality-gate architecture this ADR records; callers wire to them by SHA pin.
- [ADR-003: SAST Gate Suite](ADR-003-sast-gate-suite.md) -- static analysis (CodeQL, Semgrep) is the complementary gate suite; this ADR covers dependency, secret, IaC, and disposition scanning, deliberately not SAST.
- [ADR-005: Signing, Attestation, and Verification](ADR-005-signing-attestation-verification.md) -- the VEX gate's `actions/attest` step binds a signed OpenVEX disposition to the artifact digest via the attestation seam this ADR records.

## Links

- [OSV-Scanner](https://github.com/google/osv-scanner) -- the dependency vulnerability scanner run by `reusable-sca-osv.yml`.
- [Gitleaks](https://github.com/gitleaks/gitleaks) and [TruffleHog](https://github.com/trufflesecurity/trufflehog) -- the two secret scanners run by `reusable-secrets.yml`.
- [Trivy](https://github.com/aquasecurity/trivy) -- the IaC/license/image scanner run by `reusable-trivy.yml`.
- [Checkov](https://www.checkov.io/) -- the policy-as-code engine run by `reusable-checkov.yml`.
- [OpenVEX](https://github.com/openvex) and [vexctl](https://github.com/openvex/vexctl) -- the disposition format and tool used by `reusable-vex.yml`.

## More Information

- **Date:** 2026-06-29
- **Source:** `.github/workflows/reusable-sca-osv.yml`, `.github/workflows/reusable-secrets.yml`, `.github/workflows/reusable-trivy.yml`, `.github/workflows/reusable-checkov.yml`, `.github/workflows/reusable-vex.yml`.
- **Related ADRs:** ADR-002, ADR-003, ADR-005

## Audit

### 2026-06-29

**Status:** Compliant

**Findings:**

| Finding | Files | Lines | Assessment |
|---------|-------|-------|------------|
| OSV-Scanner runs inline (`osv-scanner-action` + `osv-reporter-action` @ `fa4ff678dd5d0a4fa3d628e57af8162873e93cd6`, v2.3.8), job name `osv-scanner`; scan step `continue-on-error: true` (soft) | `.github/workflows/reusable-sca-osv.yml` | L61-L62, L73-L88 | compliant |
| `dependency-review` is a hard PR gate: `if: github.event_name == 'pull_request'`, `actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294` (v5.0.0), `fail-on-severity` default `high` | `.github/workflows/reusable-sca-osv.yml` | L102-L117, L29-L33 | compliant |
| Gitleaks (`8.30.1`) + TruffleHog (`3.95.6`) install as checksum-verified binaries, no third-party Action | `.github/workflows/reusable-secrets.yml` | L36, L40, L70-L95 | compliant |
| Gitleaks soft-fail (`--exit-code 0`) → SARIF to code-scanning; TruffleHog `--results=verified` hard-fails on verified live secrets (`fail-on-verified` default `true`) | `.github/workflows/reusable-secrets.yml` | L97-L105, L107-L123 | compliant |
| Trivy `iac-license` job scans `misconfig,license` at `exit-code: '0'` (soft-fail) via `aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25` (v0.36.0) | `.github/workflows/reusable-trivy.yml` | L65-L86 | compliant |
| Trivy `image` job runs only when `image-ref` set, `exit-code: '1'` (fail-closed) at `severity` default `HIGH,CRITICAL` | `.github/workflows/reusable-trivy.yml` | L37-L41, L104-L122 | compliant |
| Trivy SHA pin justified by CVE-2026-33634 (force-pushed malicious tags); SHA must never be a tag | `.github/workflows/reusable-trivy.yml` | L11-L15 | compliant |
| Checkov (`3.2.524`) installed via pinned pip venv (no Action); `iac-policy` job `--soft-fail`; default framework `terraform` | `.github/workflows/reusable-checkov.yml` | L44-L48, L61-L62, L77-L101, L39-L43 | compliant |
| VEX `attest-vex` job normalizes with vexctl (`v0.4.1` via `go install`) and attests via `actions/attest@59d89421af93a897026c735860bf21b6eb4f7b26` (v4.1.0), predicate `https://openvex.dev/ns/v0.2.0`, bound to subject digest | `.github/workflows/reusable-vex.yml` | L45-L49, L55-L56, L71-L89 | compliant |
| VEX requires the OpenVEX document; job fails if absent at `vex-path` | `.github/workflows/reusable-vex.yml` | L32-L44, L76-L82 | compliant |
| Every Action `uses:` reference is a full 40-char SHA across all five workflows (checkout, upload-artifact, codeql-action/upload-sarif, setup-go, scanner/attest actions) | `.github/workflows/reusable-sca-osv.yml`, `reusable-secrets.yml`, `reusable-trivy.yml`, `reusable-checkov.yml`, `reusable-vex.yml` | all `uses:` lines | compliant |

**Summary:** The supply-chain scanning layer is delivered as five SHA-pinned
reusable workflows covering dependency vulnerabilities (OSV-Scanner +
dependency-review), secrets (Gitleaks + TruffleHog), IaC misconfiguration and
license (Trivy), IaC policy-as-code (Checkov), and OpenVEX exploitability
disposition. Most gates normalize on SARIF with the code-scanning required
check as the merge gate; verified live secrets, Trivy image vulnerabilities,
and the dependency-review PR gate hard-fail. Three of five gates avoid the org
Actions allow-list by installing checksum-verified binaries / pip / `go
install`. All Action `uses:` references are pinned to full 40-character SHAs.

**Action Required:** None.
