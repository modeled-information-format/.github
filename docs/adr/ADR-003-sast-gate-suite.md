---
title: "SAST Gate Suite (CodeQL + Semgrep + ShellCheck)"
description: "The org's static-analysis layer is three reusable SAST workflows — CodeQL (database build + security queries over source), Semgrep (pip-pinned pattern analysis of bundled MCP-server/plugin source), and ShellCheck (Red Hat Differential ShellCheck over shell hooks). All three emit SARIF 2.1.0 to the code-scanning hub and re-expose it as an artifact for the attestation seam. Callers invoke them as reusable workflows (e.g. sast.yml wires CodeQL + Semgrep); every uses: reference is a 40-char SHA."
type: adr
category: security
tags:
  - sast
  - codeql
  - semgrep
  - shellcheck
  - ci
  - security
status: accepted
created: 2026-06-29
updated: 2026-06-29
author: MIF Maintainers
project: modeled-information-format
technologies:
  - github-actions
  - codeql
  - semgrep
  - shellcheck
  - sarif
audience:
  - developers
  - architects
  - maintainers
related:
  - ADR-002-reusable-quality-gate-architecture.md
  - ADR-004-supply-chain-scanning.md
  - ADR-005-signing-attestation-verification.md
---

# ADR-003: SAST Gate Suite (CodeQL + Semgrep + ShellCheck)

## Status

Accepted

## Context

### Background and Problem Statement

The `modeled-information-format` org ships code that runs on consumers'
machines with full user privileges: bundled MCP servers, Claude Code plugin
hooks, and the Python/JavaScript validators behind the MIF toolchain. That
execution model makes a static-analysis (SAST) layer a baseline requirement —
command injection, unsafe deserialization, `eval`/`new Function`, `shell=True`
subprocess calls, and shell-script defects are direct remote-code-execution
vectors, not stylistic concerns.

No single analyzer covers that surface. Database-driven dataflow analysis
(CodeQL) is strong on the org's compiled-and-interpreted application code but
does not analyze shell. Pattern-based analysis (Semgrep) catches a different
class of source-level anti-patterns and runs without GitHub Advanced Security.
Shell hooks need a shell-specific linter. The org therefore needs a SAST layer
composed of more than one engine, each maintained once and consumed by every
repo, rather than each repo hand-rolling its own scanning steps.

### Current Limitations Before This Decision

- No org-wide static analysis. Each repo would otherwise duplicate scanning
  steps, drift in versions, and pin (or fail to pin) actions independently.
- No common SARIF output path. Without a shared convention, findings would not
  land uniformly in the GitHub code-scanning hub, and there would be no
  consistent artifact for the org's attestation seam to sign.
- Shell hooks — a real RCE vector — had no dedicated analyzer.

## Decision Drivers

### Primary Decision Drivers

1. **Defense in depth across engines**: One analyzer cannot cover application
   source, pattern-level anti-patterns, and shell scripts. The SAST layer must
   combine engines with complementary strengths.
2. **Centralize once, consume everywhere**: Gate logic lives in one place (the
   `.github` repo's reusable workflows) and every repo calls it. No duplicated
   scanning steps, no per-repo version drift.
3. **Uniform SARIF evidence**: Each gate must emit SARIF 2.1.0 to the
   code-scanning hub *and* re-expose it as a downloadable artifact, so findings
   are a consistent merge signal and a consistent input to the attestation
   seam.

### Secondary Decision Drivers

1. **Minimize allow-list and credential surface**: Prefer engines that need no
   third-party action and no registry login. Semgrep installs from PyPI at a
   pinned version into an isolated venv; CodeQL uses first-party GitHub actions.
   Only ShellCheck requires a third-party action (and an allow-list entry).
2. **Right failure mode per engine**: CodeQL's code-scanning check is a hard
   merge gate on high-severity findings; Semgrep soft-fails (reports to code
   scanning rather than failing the job) because pattern analysis cannot prove
   absence of a pattern; ShellCheck defaults to non-blocking on push.
3. **Supply-chain correctness of the gates themselves**: Every `uses:`
   reference must be a full 40-character SHA so the analysis layer is itself
   tamper-evident; the org `pin-check` gate re-verifies this per repo.

## Considered Options

### Option 1: Single analyzer (CodeQL only)

**Description**: Run only CodeQL code scanning across the org's repos.

**Advantages**:

- One first-party engine, free for public repos, native code-scanning
  integration.

**Disadvantages**:

- CodeQL does not analyze shell scripts, leaving plugin hooks (an RCE vector)
  unscanned.
- A single engine misses pattern-level findings that Semgrep's registry packs
  surface.

**Risk Assessment**:

- **Technical Risk**: Medium-High. A whole class of executable surface (shell)
  goes uncovered.

### Option 2: Inline scanning steps copied into each repo

**Description**: Each repo embeds its own CodeQL/Semgrep/ShellCheck steps
directly in its CI workflows.

**Advantages**:

- No cross-repo dependency; each repo is self-contained.

**Disadvantages**:

- Duplicated logic drifts: action SHAs, rule packs, and engine versions diverge
  per repo. Fixing a finding-handling bug means editing every repo.
- No single place to enforce the SARIF artifact convention the attestation seam
  depends on.

**Risk Assessment**:

- **Technical Risk**: Medium. Maintenance burden and inevitable drift weaken
  the guarantee over time.

### Option 3: Three reusable SAST workflows consumed by callers (chosen)

**Description**: Maintain three reusable workflows in the `.github` repo —
`reusable-sast-codeql.yml`, `reusable-semgrep.yml`, `reusable-shellcheck.yml`
— each `workflow_call`-only, each emitting SARIF to the code-scanning hub and
re-exposing it as an artifact. Callers invoke them as thin SHA-pinned jobs
(e.g. `sast.yml` wires CodeQL + Semgrep; ShellCheck is wired by the repo's CI
caller alongside the other gates).

**Advantages**:

- Complementary engines cover application source, pattern anti-patterns, and
  shell scripts.
- Gate logic and the SARIF/artifact convention live in one place.
- Each gate carries the right failure mode (hard gate, soft-fail, or
  non-blocking-on-push) without per-repo reinvention.

**Disadvantages**:

- ShellCheck depends on a third-party action
  (`redhat-plumbers-in-action/differential-shellcheck`), which must be on the
  org Actions allow-list before the reusable runs.

**Risk Assessment**:

- **Technical Risk**: Low. Each reusable is independently auditable and
  SHA-pinned; the only third-party dependency is allow-listed and pinned.

## Decision

The org's SAST layer is three reusable workflows in the `.github` repo, each
`workflow_call`-only and each emitting SARIF 2.1.0 to the GitHub code-scanning
hub plus a downloadable SARIF artifact for the attestation seam. Callers invoke
them as thin jobs.

**CodeQL — `reusable-sast-codeql.yml` (`name: sast-codeql`).** Builds a CodeQL
database (AST + dataflow + control-flow) and runs security queries. Inputs:
`languages` (required), `build-mode` (default `none`, suited to interpreted
languages), `config-file`, and `queries` (optional suite, e.g.
`security-extended`). Single job `analyze` on `ubuntu-latest` with
`security-events: write`, `contents: read`, `actions: read`, `packages: read`.
Steps: checkout
(`actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0`, v7.0.0), init and
analyze (`github/codeql-action/init` and `.../analyze`, both
`@8aad20d150bbac5944a9f9d289da16a4b0d87c1e`, v4.36.2), a `jq` merge of the
per-language SARIF runs into a single `results.sarif`, and upload
(`actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`, v7.0.1) as
artifact `sast-sarif`. On a pull request the "Code scanning results" check
fails on error/critical/high findings — wired as a required status check it is
a hard merge gate.

**Semgrep — `reusable-semgrep.yml` (`name: semgrep`).** Pattern-based SAST over
bundled MCP-server/plugin source. Inputs: `directory` (default `.`), `config`
(default registry packs `p/security-audit p/secrets p/command-injection`), and
`semgrep-version` (default `1.139.0`, pinned, no range). Single job `sast-code`
on `ubuntu-latest` with `contents: read`, `security-events: write`,
`actions: read`. Semgrep installs from PyPI into an isolated venv (no
third-party action, no allow-list entry, no login token). The scan is
**soft-fail** (`--no-error` plus `|| true`): findings are reported to code
scanning — the gate — rather than failing the job, because pattern analysis
suppresses findings near partial safety checks and cannot prove absence of a
pattern across files. SARIF uploads via
`github/codeql-action/upload-sarif@8aad20d150bbac5944a9f9d289da16a4b0d87c1e`
(v4.36.2) and as artifact `sast-code-sarif`
(`actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`, v7.0.1).

**ShellCheck — `reusable-shellcheck.yml` (`name: shellcheck`).** SAST for shell
scripts (plugin hooks run as arbitrary shell at PreToolUse/PostToolUse/Stop).
Input: `strict-on-push` (boolean, default `false`). Single job `sast-hooks` on
`ubuntu-latest` with `contents: read`, `security-events: write`. It runs Red
Hat's Differential ShellCheck in full-tree mode
(`redhat-plumbers-in-action/differential-shellcheck@d965e66ec0b3b2f821f75c8eff9b12442d9a7d1e`,
v5.5.6, `diff-scan: false`), which emits native SARIF to the code-scanning hub;
the reusable normalizes that to `shellcheck.sarif` (substituting an empty SARIF
skeleton if the action produced none) and uploads it as artifact
`sast-hooks-sarif`. Checkout uses `fetch-depth: 0`. This is the only SAST
engine that depends on a third-party action, which must be on the org Actions
allow-list (`redhat-plumbers-in-action/*`).

**Caller wiring — `sast.yml`.** The `.github` repo dogfoods its own reusables:
`sast.yml` (`name: sast`) runs on `pull_request` and `push` to `main`, a weekly
schedule (`cron: '37 4 * * 1'`, Monday 04:37 UTC), and `workflow_dispatch`. It
defines two jobs — `codeql` (calls `reusable-sast-codeql.yml` with
`languages: 'python,javascript-typescript'`) and `semgrep` (calls
`reusable-semgrep.yml` with `directory: .`). In this central repo the reusables
are referenced by **local `./` path**, which is exempt from SHA-pinning and
`pin-check`; downstream caller repos instead pin the reusables to a full
40-character SHA. ShellCheck is invoked by the CI caller alongside the other
quality gates rather than inside `sast.yml`.

Each reusable declares a top-level `permissions: contents: read` floor and
grants only the additional scopes its job needs. All `uses:` references in the
reusables are full 40-character SHAs, consistent with the org's fail-closed,
SHA-pinned posture.

## Consequences

### Positive

1. **Layered coverage**: Application source (CodeQL), pattern anti-patterns
   (Semgrep), and shell hooks (ShellCheck) are each analyzed by a fit-for-
   purpose engine.
2. **Single source of truth**: Engine versions, rule packs, action SHAs, and
   the SARIF/artifact convention are maintained once and consumed by every
   repo.
3. **Uniform attestable evidence**: Every gate emits SARIF to the code-scanning
   hub and a named SARIF artifact (`sast-sarif`, `sast-code-sarif`,
   `sast-hooks-sarif`), giving the attestation seam a consistent verdict input.
4. **Calibrated failure modes**: CodeQL is a hard merge gate; Semgrep soft-
   fails to avoid blocking on unprovable absence; ShellCheck is non-blocking on
   push by default — each matched to what the engine can actually prove.

### Negative

1. **Third-party allow-list dependency**: ShellCheck requires
   `redhat-plumbers-in-action/differential-shellcheck` on the org Actions
   allow-list; the reusable cannot run until that entry exists.
2. **Soft-fail visibility**: Because Semgrep does not fail the job, a
   regression it catches surfaces only in the code-scanning hub, not as a red
   job — it must be watched there (or promoted to a required check) to act as a
   gate.

### Neutral

1. **Pinned engine versions need deliberate updates**: Semgrep is pinned to an
   exact version and the actions to exact SHAs. Upgrades are explicit edits —
   the correct supply-chain posture, but not automatic.
2. **Caller-side pinning obligation**: Downstream repos must pin the reusables
   to a full SHA (the central repo's local `./` references are the documented
   exception); `pin-check` enforces this per repo.

## Decision Outcome

The org runs three reusable SAST gates — CodeQL, Semgrep, and ShellCheck —
each emitting SARIF 2.1.0 to the code-scanning hub and a named SARIF artifact.
Callers invoke them as thin jobs; `sast.yml` wires CodeQL
(`python,javascript-typescript`) and Semgrep, while ShellCheck is wired by the
CI caller. All `uses:` references are full 40-character SHAs.

### Implementation

**Calling the reusables (downstream caller, SHA-pinned):**

```yaml
jobs:
  sast:
    permissions:
      security-events: write
      contents: read
      actions: read
    uses: modeled-information-format/.github/.github/workflows/reusable-sast-codeql.yml@<sha>
    with:
      languages: 'javascript-typescript,python'
```

**Required-status-check contexts** (format: `<caller-job-id> / <called-job-name>`):

From a caller wiring all three: `codeql / analyze`, `semgrep / sast-code`,
`shellcheck / sast-hooks`. In the `.github` repo's own `sast.yml` the jobs are
`codeql` and `semgrep` (the "Code scanning results" check, or
`sast / codeql` / `sast / semgrep`, can be made required on the default
branch).

**SARIF artifacts (attestation-seam inputs):** `sast-sarif` (CodeQL,
`results.sarif`), `sast-code-sarif` (Semgrep, `semgrep.sarif`),
`sast-hooks-sarif` (ShellCheck, `shellcheck.sarif`).

**Workflow files:** `.github/workflows/reusable-sast-codeql.yml`,
`.github/workflows/reusable-semgrep.yml`,
`.github/workflows/reusable-shellcheck.yml`, `.github/workflows/sast.yml`.

## Related Decisions

- [ADR-002: Reusable Quality-Gate Architecture](ADR-002-reusable-quality-gate-architecture.md) -- the SAST gates are members of the central reusable-workflow suite this ADR establishes; the `workflow_call` + SARIF-artifact convention is inherited from it.
- [ADR-004: Supply-Chain Scanning](ADR-004-supply-chain-scanning.md) -- the SCA/secrets/IaC gates are the non-SAST half of the org's scanning layer; SAST covers source-level code defects, ADR-004 covers dependency and configuration risk.
- [ADR-005: Signing, Attestation, and Verification](ADR-005-signing-attestation-verification.md) -- the SARIF artifacts each SAST gate exposes (`sast-sarif`, `sast-code-sarif`, `sast-hooks-sarif`) are the verdict inputs the attestation seam signs.

## Links

- [CodeQL](https://codeql.github.com/) -- the database-driven analysis engine run by `reusable-sast-codeql.yml`.
- [Semgrep](https://semgrep.dev/) -- the pattern-based analysis engine run by `reusable-semgrep.yml`.
- [ShellCheck](https://www.shellcheck.net/) -- the shell-script analyzer wrapped by Differential ShellCheck in `reusable-shellcheck.yml`.
- [Differential ShellCheck action](https://github.com/redhat-plumbers-in-action/differential-shellcheck) -- the third-party action that runs ShellCheck and emits SARIF.
- [SARIF 2.1.0 specification](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html) -- the evidence format all three gates emit.

## More Information

- **Date:** 2026-06-29
- **Source:** `.github/workflows/reusable-sast-codeql.yml`, `.github/workflows/reusable-semgrep.yml`, `.github/workflows/reusable-shellcheck.yml`, `.github/workflows/sast.yml`.
- **Related ADRs:** ADR-002, ADR-004, ADR-005

## Audit

### 2026-06-29

**Status:** Compliant

**Findings:**

| Finding | Files | Lines | Assessment |
|---------|-------|-------|------------|
| CodeQL reusable is `workflow_call`-only (`name: sast-codeql`), inputs `languages` (required), `build-mode` (default `none`), `config-file`, `queries` | `.github/workflows/reusable-sast-codeql.yml` | L25-L48 | compliant |
| CodeQL job `analyze` on `ubuntu-latest`; permissions `security-events: write`, `contents: read`, `actions: read`, `packages: read` | `.github/workflows/reusable-sast-codeql.yml` | L60-L68 | compliant |
| CodeQL pinned actions: checkout `@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0` (v7.0.0); init/analyze `@8aad20d150bbac5944a9f9d289da16a4b0d87c1e` (v4.36.2); upload-artifact `@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` (v7.0.1) | `.github/workflows/reusable-sast-codeql.yml` | L71, L74, L82, L109 | compliant |
| CodeQL merges per-language SARIF via `jq` into `results.sarif`, exposed as artifact `sast-sarif` | `.github/workflows/reusable-sast-codeql.yml` | L91-L113 | compliant |
| Semgrep reusable is `workflow_call`-only (`name: semgrep`), inputs `directory` (default `.`), `config` (default `p/security-audit p/secrets p/command-injection`), `semgrep-version` (default `1.139.0`) | `.github/workflows/reusable-semgrep.yml` | L28-L54 | compliant |
| Semgrep job `sast-code`; installed from PyPI into isolated venv (no third-party action / allow-list entry) | `.github/workflows/reusable-semgrep.yml` | L60-L79 | compliant |
| Semgrep is soft-fail (`--no-error` plus `|| true`); code scanning is the gate | `.github/workflows/reusable-semgrep.yml` | L81-L97 | compliant |
| Semgrep SARIF uploaded via `github/codeql-action/upload-sarif@8aad20d150bbac5944a9f9d289da16a4b0d87c1e` (v4.36.2) and as artifact `sast-code-sarif` | `.github/workflows/reusable-semgrep.yml` | L99-L112 | compliant |
| ShellCheck reusable is `workflow_call`-only (`name: shellcheck`), input `strict-on-push` (boolean, default `false`); job `sast-hooks` | `.github/workflows/reusable-shellcheck.yml` | L21-L48 | compliant |
| ShellCheck runs Differential ShellCheck `@d965e66ec0b3b2f821f75c8eff9b12442d9a7d1e` (v5.5.6, `diff-scan: false`); third-party action requiring org allow-list | `.github/workflows/reusable-shellcheck.yml` | L9-L11, L55-L61 | compliant |
| ShellCheck normalizes SARIF to `shellcheck.sarif` (empty skeleton fallback) and uploads artifact `sast-hooks-sarif` | `.github/workflows/reusable-shellcheck.yml` | L63-L81 | compliant |
| `sast.yml` triggers: PR + push to `main`, weekly schedule `37 4 * * 1`, `workflow_dispatch` | `.github/workflows/sast.yml` | L14-L21 | compliant |
| `sast.yml` job `codeql` calls CodeQL reusable with `languages: 'python,javascript-typescript'`; job `semgrep` calls Semgrep reusable with `directory: .`; local `./` references exempt from pin-check | `.github/workflows/sast.yml` | L8-L11, L27-L46 | compliant |

**Summary:** The org's SAST layer is three reusable workflows — CodeQL,
Semgrep, and ShellCheck — each `workflow_call`-only, each emitting SARIF 2.1.0
to the code-scanning hub and a named downloadable artifact for the attestation
seam. CodeQL is a hard merge gate on high-severity findings; Semgrep soft-fails
(code scanning is the gate) and needs no third-party action; ShellCheck wraps
the allow-listed Differential ShellCheck action. `sast.yml` wires CodeQL and
Semgrep via local `./` references in the central repo; downstream callers pin
the reusables to full SHAs. All `uses:` references in the reusables are full
40-character SHAs.

**Action Required:** None.
