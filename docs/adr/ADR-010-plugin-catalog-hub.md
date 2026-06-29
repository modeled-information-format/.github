---
title: "Plugin Catalog Hub and Manifest Review"
description: "The org governs Claude Code plugin marketplaces with three distinct mechanisms: a scheduled verify-first catalog-update hub that re-pins external plugin entries to their latest attested release and opens zero-touch auto-merge PRs; a reusable soft-fail manifest-review gate that enforces structural integrity (40-char SHA pins, reserved-name rejection, required fields) and normalizes findings to SARIF; and a hard-fail catalog-check gate that keeps the attested-delivery workflow catalog in sync with the reusable workflows on disk. A deny-list scopes the hub. Every action is SHA-pinned."
type: adr
category: process
tags:
  - plugin-catalog
  - manifest-review
  - automation
  - security
  - governance
status: accepted
created: 2026-06-29
updated: 2026-06-29
author: MIF Maintainers
project: modeled-information-format
technologies:
  - github-actions
  - sigstore
  - slsa
  - sarif
  - python
audience:
  - developers
  - architects
  - maintainers
related:
  - ADR-002-reusable-quality-gate-architecture.md
---

# ADR-010: Plugin Catalog Hub and Manifest Review

## Status

Accepted

## Context

### Background and Problem Statement

The org distributes Claude Code plugins through marketplace catalogs
(`.claude-plugin/marketplace.json`). Each catalog lists plugin entries; external
entries reference another repository's content pinned to a specific commit. Two
governance problems follow from this model.

First, an external plugin pin can silently rot or be rug-pulled: a catalog that
points a `github`, `url`, or `git-subdir` source at a mutable ref (a branch or a
tag that can move) gives a consumer no guarantee that the content installed today
matches the content reviewed yesterday. Keeping every external pin current *and*
attested is ongoing work that no existing ecosystem tool performs — Dependabot
cannot parse the custom `git-subdir` + 40-character `sha` pin scheme, and Git
submodule tracking follows branch HEAD rather than attested release tags
(`catalog-update/README.md` L1-L13).

Second, a marketplace catalog or a plugin manifest can drift out of structural
integrity: an external source can lose its SHA pin, a marketplace `name` can
collide with an Anthropic-reserved namespace, or a manifest can omit a required
field. These are integrity invariants the marketplace depends on, and they need a
gate that runs on every contribution.

A third, related hygiene concern is internal to the `.github` repo itself: the
attested-delivery skill ships a hand-maintained `workflow-catalog.md` that
documents the org's reusable (`workflow_call`) workflows. A hand-maintained index
drifts — "docs say 14, repo ships 19" — unless a gate keeps it honest
(`.github/workflows/catalog-check.yml` L1-L5).

This ADR records the three mechanisms already in production that address these
problems, and the deny-list that scopes the first of them.

### Current Limitations Before This Decision

- External plugin pins in marketplace catalogs had no automated, attestation-aware
  update path. Bringing a pin current meant a manual edit with no enforced proof
  that the new target was attested.
- No gate enforced the marketplace/manifest structural invariants (SHA-pinned
  external sources, non-reserved marketplace names, required fields) on
  contribution.
- The attested-delivery workflow catalog was a hand-maintained document with no
  check that it matched the reusable workflows actually present on disk.

## Decision Drivers

### Primary Decision Drivers

1. **Verify before propose**: An automated re-pin must never advance a release
   whose attestations do not verify. The candidate release's attestations are
   checked fail-closed *before* a PR is opened, so the thing that was verified is
   the thing that runs.
2. **Least-privilege cross-repo writes**: The hub touches other repositories. Its
   write credential must be scoped to one target repo at a time, and the merge
   control must live in the target repo, not in the hub.
3. **Structural integrity as a contribution gate**: Every marketplace catalog and
   plugin manifest must be checked for the invariants the marketplace depends on —
   above all that external sources are pinned to a full 40-character SHA, which
   defeats rug-pull catalog updates.

### Secondary Decision Drivers

1. **Opt-in by capability, not by registry**: Adding a marketplace to the hub's
   scope should require no registry file to maintain. Installing the org App on a
   repo *is* the opt-in, so the hub can never reach beyond where its credential
   already has access.
2. **Dependency-free gate logic**: The manifest-review gate should not require a
   third-party action or an allow-list entry; pure standard-library Python keeps
   the gate auditable and free of supply-chain surface.
3. **No silent index drift**: The reusable-workflow catalog must be machine-checked
   in both directions — every reusable is documented, every documented entry
   resolves to a real file.

## Considered Options

### Option 1: Manual external-pin maintenance (status quo)

**Description**: Update external plugin pins by hand, relying on reviewer
diligence to confirm the new target is attested.

**Advantages**:

- No automation to build or maintain.

**Disadvantages**:

- No enforced proof that an updated pin points at an attested release.
- Pins rot; no schedule brings them current.

**Risk Assessment**:

- **Technical Risk**: High. A stale or unverified pin is indistinguishable from a
  current, attested one at review time.

### Option 2: Reuse Dependabot or Git submodules for catalog updates

**Description**: Delegate catalog-pin updates to an existing ecosystem tool.

**Advantages**:

- No bespoke mechanism.

**Disadvantages**:

- No ecosystem parses the custom `git-subdir` + 40-char `sha` pin scheme inside
  `marketplace.json`, so Dependabot cannot update these entries
  (`catalog-update/README.md` L4-L7).
- Submodule tracking follows branch HEAD, not attested release tags — the wrong
  semantics for a verify-first pin.

**Risk Assessment**:

- **Technical Risk**: Medium. The tools do not understand the pin model and would
  track mutable refs.

### Option 3: Verify-first catalog hub plus reusable manifest review and a catalog-completeness gate (chosen)

**Description**: Run three mechanisms. (a) A scheduled `plugin-catalog-update-hub`
that discovers every App-accessible marketplace, re-pins each external entry to its
latest *attested* release after a fail-closed attestation check, and opens a
zero-touch auto-merge PR whose body carries the attestation evidence. (b) A
reusable `manifest-review` workflow that enforces marketplace/manifest structural
invariants, soft-fails, and normalizes findings to SARIF + a `manifest/v1`
attestation-seam verdict. (c) A `catalog-check` gate that hard-fails when the
attested-delivery `workflow-catalog.md` and the reusable workflows on disk drift
apart. A `deny-list.yaml` scopes the hub.

**Advantages**:

- Verify-first: only releases whose attestations verify are ever proposed.
- Least-privilege: per-target-scoped App tokens; the merge control is each
  target's own fail-closed `catalog-admission` gate.
- The manifest gate is dependency-free (standard-library Python; no allow-list
  entry) and non-blocking, surfacing findings without halting contribution.
- The catalog-completeness gate prevents index drift in both directions.

**Disadvantages**:

- Three mechanisms with distinct fail postures (verify-first, soft-fail,
  hard-fail) must each be understood on its own terms; a single "fail-closed"
  mental model does not describe all three.

**Risk Assessment**:

- **Technical Risk**: Low. Each mechanism is independently auditable; the hub
  proposes but does not merge, and the target repo's gate is the merge control.

## Decision

The org governs plugin marketplaces with three mechanisms, each SHA-pinning every
action `uses:` reference, plus a deny-list that scopes the hub.

**Catalog-update hub (`.github/workflows/plugin-catalog-update-hub.yml`).** A
central, verify-first updater. It triggers on a weekly schedule
(`cron: "37 6 * * 1"`, Mondays at a scattered minute) and on `workflow_dispatch`
with `dry-run` and single-`repo` inputs (L14-L27). The `discover` job
(`name: discover marketplaces`) mints an installation token via
`actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1`
(v3.2.0) using the `CATALOG_UPDATER_APP_CLIENT_ID` org variable and the
`CATALOG_UPDATER_APP_PRIVATE_KEY` org secret, enumerates
`installation/repositories`, drops any `owner/repo` on the deny-list, and keeps
only repos that carry `.claude-plugin/marketplace.json` — building a matrix
(L32-L96). The `update` job (`name: update ${{ matrix.repo }}`) mints a fresh App
token **scoped to the single target repo** (`repositories: ${{ matrix.name }}`),
checks out that marketplace, sparse-checks-out the composite action, and runs the
verify-first re-pin in `mode: update`, honoring `dry-run` (L98-L139).

Per external entry, the composite engine resolves the source repo's latest release,
dereferences the tag to a commit SHA, **verifies the release's attestations
fail-closed** (`gh attestation verify`) and advances only a release whose every
required predicate verifies, re-pins `source.sha` + `source.ref` with a surgical
text edit, and opens an auto-merge PR (`deps/external-plugin/<name>`) carrying the
attestation evidence (`catalog-update/README.md` L36-L50). The default required
predicate is SLSA build provenance (`https://slsa.dev/provenance/v1`); more can be
required via `predicate-types` (README L53-L58). The hub proposes; it does not
merge. The merge control is the **target repo's** fail-closed `catalog-admission`
gate, which re-verifies on the PR (README L49-L51).

**Reusable manifest review (`.github/workflows/reusable-manifest-review.yml`).** A
`workflow_call` reusable that reviews the marketplace catalog and each plugin
manifest for the structural integrity invariants the marketplace depends on. It
takes a `directory` input (default `.`) and outputs a SARIF artifact
(`manifest-sarif` / `manifest-review.sarif`) (L27-L41). The job runs pure
standard-library Python (no install, no third-party action, no allow-list entry)
and is **soft-fail**: it reports findings, it does not fail the job (L11-L12). It
checks that every external (object) plugin source — `github`, `url`, or
`git-subdir` — is pinned to a 40-character SHA (rule `MR006`, L109-L115); that the
marketplace `name` is not an Anthropic-reserved name (rule `MR003` against the
`RESERVED` set, L98-L101); and that `marketplace.json` and every `plugin.json`
carry their required fields (`MR002`/`MR004`/`MR005`/`MR008`/`MR009`). Findings
normalize to SARIF and upload to the code-scanning hub via
`github/codeql-action/upload-sarif@8aad20d150bbac5944a9f9d289da16a4b0d87c1e`
(v4.36.2), with the SARIF also kept as an artifact via
`actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` (v7.0.1)
(L140-L153). The verdict seam-attests as `manifest/v1`.

**Catalog-completeness gate (`.github/workflows/catalog-check.yml`).** A repo-CI
gate (not itself a reusable) that keeps the attested-delivery skill's
`workflow-catalog.md` honest. It triggers on `pull_request` and `push` to `main`
when either the workflows directory or the catalog file changes (L8-L17), and
hard-fails (`exit 1`). It checks both directions: forward — every
`workflow_call` reusable under `.github/workflows/` must have a catalog entry
(L39-L48); reverse — every workflow the catalog names must resolve to a real file
on disk (L50-L58). This is the gate that prevents the "docs say 14, repo ships 19"
drift a hand-maintained index accumulates.

**Deny-list (`catalog-update/deny-list.yaml`).** A safety valve for the hub:
`owner/repo` names the hub must never touch, even when the App is installed and a
`marketplace.json` is present. It is parsed in the hub's `discover` job and applied
before matrix construction; it is currently empty (`deny: []`, L8). Opt-in to the
hub is App installation, not a registry edit; opt-out is uninstalling the App or
adding the repo here (`catalog-update/README.md` L23-L33).

## Consequences

### Positive

1. **Verify-first re-pins**: External plugin pins are brought current automatically,
   and only against releases whose attestations verify fail-closed.
2. **Least-privilege automation**: The hub writes with per-target-scoped App
   tokens and proposes PRs only; the merge decision stays with each target's own
   `catalog-admission` gate.
3. **Dependency-free integrity gate**: `manifest-review` enforces SHA-pinning,
   reserved-name rejection, and required fields with standard-library Python and
   no allow-list cost, and surfaces findings as SARIF without blocking.
4. **No index drift**: `catalog-check` guarantees the reusable-workflow catalog and
   the workflows on disk stay in one-to-one correspondence.

### Negative

1. **Three distinct fail postures**: The hub is verify-first, `manifest-review` is
   soft-fail, and `catalog-check` is hard-fail. Operators must hold the three apart
   rather than assume a uniform posture.
2. **App-install discovery is implicit**: Because opt-in is App installation,
   adding the App org-wide silently widens the hub's scope; the deny-list is the
   only brake and must be maintained when broad installation is in effect.

### Neutral

1. **Soft-fail by design**: `manifest-review` does not block a PR on findings; the
   findings live in code-scanning and the `manifest/v1` verdict. Enforcement, where
   wanted, is a branch-protection decision layered on top, not a property of the
   gate itself.
2. **Engine internals are out of this ADR's scope**: The composite action's engine
   (`catalog_update.py`) and the target-side `catalog-admission` gate are described
   by behavior (README and hub caller) rather than by line-level citation here.

## Decision Outcome

Plugin marketplaces in the org are governed by a verify-first catalog-update hub,
a soft-fail reusable manifest-review gate, and a hard-fail catalog-completeness
gate, with a deny-list scoping the hub. Every action `uses:` reference across the
three workflows is pinned to a full 40-character SHA.

### Implementation

**Dry-run the hub (resolve + verify + render, open/merge nothing):**

```bash
gh workflow run plugin-catalog-update-hub.yml -f dry-run=true
```

**Call the reusable manifest-review gate from a repo:**

```yaml
jobs:
  manifest-review:
    permissions:
      contents: read
      security-events: write
      actions: read
    uses: modeled-information-format/.github/.github/workflows/reusable-manifest-review.yml@<sha>
    with:
      directory: .
```

**Manifest-review SARIF outputs:** artifact `manifest-sarif`, filename
`manifest-review.sarif`, code-scanning category `manifest-review`.

**Owner setup for the hub** (org variable + org secret, scoped to `.github`):

```bash
gh variable set CATALOG_UPDATER_APP_CLIENT_ID --org modeled-information-format \
  --visibility selected --repos .github --body "<CLIENT_ID>"
gh secret set CATALOG_UPDATER_APP_PRIVATE_KEY --org modeled-information-format \
  --visibility selected --repos .github < ~/.secrets/modeled-information-format-ci.pem
```

**Workflow files:** `.github/workflows/plugin-catalog-update-hub.yml`,
`.github/workflows/reusable-manifest-review.yml`,
`.github/workflows/catalog-check.yml`. **Supporting files:**
`catalog-update/deny-list.yaml`, `catalog-update/README.md`.

## Related Decisions

- [ADR-002: Reusable Quality-Gate Architecture](ADR-002-reusable-quality-gate-architecture.md) -- `reusable-manifest-review.yml` is one of the org's central `workflow_call` reusables; the `catalog-check` gate enforces that every such reusable is documented in the attested-delivery workflow catalog.

## Links

- [Attested catalog-updater README](https://github.com/modeled-information-format/.github/blob/main/catalog-update/README.md) -- the verify-first, opt-in-by-App-install design of the hub and the per-entry re-pin sequence.
- [SLSA Build Provenance specification](https://slsa.dev/provenance/v1) -- the default required predicate the hub verifies before re-pinning.
- [SARIF 2.1.0 specification](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html) -- the format `manifest-review` normalizes findings to for the code-scanning hub.

## More Information

- **Date:** 2026-06-29
- **Source:** `.github/workflows/catalog-check.yml`, `.github/workflows/plugin-catalog-update-hub.yml`, `.github/workflows/reusable-manifest-review.yml`, `catalog-update/README.md`, `catalog-update/deny-list.yaml`.
- **Related ADRs:** ADR-002

## Audit

### 2026-06-29

**Status:** Compliant

**Findings:**

| Finding | Files | Lines | Assessment |
|---------|-------|-------|------------|
| Hub triggers on weekly schedule (`cron: "37 6 * * 1"`) and `workflow_dispatch` with `dry-run` + `repo` inputs | `.github/workflows/plugin-catalog-update-hub.yml` | L14-L27 | compliant |
| `discover` job mints an installation token via `actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1` (v3.2.0) and enumerates `installation/repositories` | `.github/workflows/plugin-catalog-update-hub.yml` | L44-L87 | compliant |
| Deny-list parsed and applied (`is_denied` skip) before matrix construction; only repos carrying `.claude-plugin/marketplace.json` are kept | `.github/workflows/plugin-catalog-update-hub.yml` | L60-L96 | compliant |
| `update` job mints a per-target-scoped App token (`repositories: ${{ matrix.name }}`) and runs the verify-first re-pin composite action in `mode: update` honoring `dry-run` | `.github/workflows/plugin-catalog-update-hub.yml` | L98-L139 | compliant |
| Per-entry sequence: resolve latest release → deref tag to SHA → verify attestations fail-closed → re-pin → auto-merge PR; default predicate SLSA provenance; merge control is the target's `catalog-admission` | `catalog-update/README.md` | L36-L58 | compliant |
| Opt-in is App installation (no registry file); opt-out is uninstall or deny-list entry | `catalog-update/README.md` | L23-L33 | compliant |
| Deny-list is the hub safety valve; currently empty (`deny: []`) | `catalog-update/deny-list.yaml` | L8 | compliant |
| `manifest-review` is a `workflow_call` reusable with `directory` input and SARIF outputs (`manifest-sarif` / `manifest-review.sarif`) | `.github/workflows/reusable-manifest-review.yml` | L27-L41 | compliant |
| `manifest-review` is soft-fail (report, don't fail the job); pure standard-library Python, no third-party action, no allow-list entry | `.github/workflows/reusable-manifest-review.yml` | L1-L12 | compliant |
| External plugin sources (`github`/`url`/`git-subdir`) must be pinned to a 40-char SHA (rule MR006) | `.github/workflows/reusable-manifest-review.yml` | L109-L115 | compliant |
| Marketplace `name` rejected if Anthropic-reserved (rule MR003 against the `RESERVED` set) | `.github/workflows/reusable-manifest-review.yml` | L67-L101 | compliant |
| Required-field checks on `marketplace.json` and `plugin.json` (rules MR002/MR004/MR005/MR008/MR009) | `.github/workflows/reusable-manifest-review.yml` | L98-L126 | compliant |
| Findings upload to code-scanning via `github/codeql-action/upload-sarif@8aad20d150bbac5944a9f9d289da16a4b0d87c1e` (v4.36.2) and an artifact via `actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` (v7.0.1) | `.github/workflows/reusable-manifest-review.yml` | L140-L153 | compliant |
| `catalog-check` triggers on PR and push-to-main when workflows or the catalog change; permissions `contents: read` | `.github/workflows/catalog-check.yml` | L8-L20 | compliant |
| `catalog-check` forward direction: every `workflow_call` reusable must have a `workflow-catalog.md` entry | `.github/workflows/catalog-check.yml` | L39-L48 | compliant |
| `catalog-check` reverse direction: every catalog-named workflow must resolve to a real file; hard-fail `exit 1` on drift | `.github/workflows/catalog-check.yml` | L50-L63 | compliant |
| All three workflows pin `actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0` (v7.0.0) | `.github/workflows/catalog-check.yml`, `plugin-catalog-update-hub.yml`, `reusable-manifest-review.yml` | catalog-check L30; hub L42, L119, L126; manifest-review L56 | compliant |

**Summary:** Three production mechanisms govern the org's plugin marketplaces.
The `plugin-catalog-update-hub` re-pins external plugin entries verify-first
against attested releases and opens least-privilege, zero-touch auto-merge PRs;
the reusable `manifest-review` gate enforces SHA-pinning, reserved-name rejection,
and required-field invariants as soft-fail SARIF; and `catalog-check` hard-fails
on any drift between the attested-delivery workflow catalog and the reusable
workflows on disk. A deny-list scopes the hub. Every action `uses:` reference is
pinned to a full 40-character SHA.

**Action Required:** None.
