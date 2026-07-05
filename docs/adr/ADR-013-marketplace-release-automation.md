---
title: "Automated Attested Marketplace Release on Catalog Admission"
description: "Extends ADR-010's pipeline past the admission-verified merge: a reusable workflow, called by each marketplace on catalog-path pushes to main, computes the next patch version and pushes the tag with a release-App token, firing the existing tag-gated attested release unchanged."
type: adr
category: process
tags:
  - plugin-catalog
  - release
  - automation
  - security
  - governance
status: accepted
created: 2026-07-05
updated: 2026-07-05
author: MIF Maintainers
project: modeled-information-format
technologies:
  - github-actions
  - sigstore
  - slsa
audience:
  - developers
  - architects
  - maintainers
related:
  - ADR-005-signing-attestation-verification.md
  - ADR-010-plugin-catalog-hub.md
  - ADR-011-least-privilege-app-fleet.md
---

# ADR-013: Automated Attested Marketplace Release on Catalog Admission

## Status

Accepted

## Context

### Background and Problem Statement

ADR-010 established the org's plugin-catalog pipeline: separately-released
plugins are built and attested in their own repos (ADR-005); the catalog-update
hub re-pins each marketplace's external entries to the latest attested release
verify-first and opens an auto-merge PR; the marketplace's fail-closed
`catalog-admission` gate re-verifies on that PR and is the merge control. The
pipeline's terminal step is the admission-verified merge: an updated
`.claude-plugin/marketplace.json` lands on `main`, and nothing further happens.

The marketplace repo, however, has its own attested release pipeline
(`claude-code-plugins/.github/workflows/release.yml`): tarball build,
SLSA build provenance, CycloneDX SBOM, seam-attested gate verdicts, a cosign
keyless-signed `marketplace.json`, OpenVEX, an in-run fail-closed verify, and a
tag-gated publish. That pipeline triggers only on a human-pushed `v*.*.*` tag
(or a `workflow_dispatch` dry-run that publishes nothing).

The two halves do not meet. After an admitted catalog change merges, the
catalog on `main` and the catalog in the latest signed release diverge, and
stay diverged until a human remembers to tag. A consumer who does the right
thing — verifying the released, cosign-signed catalog rather than trusting
branch HEAD — gets the *stale* catalog: the newest attested plugin release is
referenced by `main` but by no signed marketplace release. The stronger a
consumer's verification discipline, the longer they wait for the update the
pipeline already admitted.

### Current Limitations Before This Decision

- No mechanism converts an admitted catalog state into a marketplace release.
  The hub→admission flow ends at the merge; `release.yml` starts at a tag; no
  automation connects them.
- No automated version bump exists. The marketplace's version identity is its
  git tag (the catalog file itself carries no version field), and the next tag
  is computed by a human, ad hoc.
- The staleness window between an admitted catalog change and its attested
  release is unbounded — it lasts until someone notices.

## Decision Drivers

### Primary Decision Drivers

1. **Every admitted catalog state becomes an attested release**: WHEN a change
   to `.claude-plugin/marketplace.json` lands on the marketplace's `main`, the
   marketplace SHALL publish a release whose artifacts embed that catalog state
   and whose attestations verify fail-closed. The staleness window becomes one
   pipeline run, not one human memory.
2. **Reuse the existing release pipeline unchanged**: the new mechanism SHALL
   supply only the trigger (a version tag); build, attest, sign, verify, and
   publish logic stays in the marketplace's existing tag-gated `release.yml`.
   The invariant "a tag publishes nothing unattested" must survive intact.
3. **Least privilege and structural non-recursion**: the tag SHALL be minted
   with the org `release` App's per-repo-scoped token (ADR-011), and the
   automation SHALL be structurally incapable of triggering itself — the
   trigger set it listens on (branch pushes) and the ref set it writes (tags)
   must not intersect.

### Secondary Decision Drivers

1. **One implementation, every marketplace**: the org runs more than one
   marketplace (`claude-code-plugins` and `gdlc`); per ADR-002 the mechanism
   belongs in `.github` as a reusable workflow consumed through thin SHA-pinned
   callers.
2. **Human override preserved**: automation covers the routine case (patch
   bumps for admitted catalog changes); minor/major version decisions remain
   human, via a manual dispatch input or a manually pushed tag, and a
   human-pushed tag on the same commit suppresses the automatic one.
3. **The version identity stays the git tag**: the automation SHALL NOT write a
   version back into the repository's files — no version-stamp commit to
   `main`, no self-referential trigger surface.

## Considered Options

### Option 1: Status quo — human tags after admission (rejected)

**Description**: Keep the pipeline as ADR-010 left it; a maintainer pushes
`v*.*.*` when they decide a release is due.

**Advantages**:

- Nothing to build; release cadence under direct human control.

**Disadvantages**:

- The exact gap this ADR exists to close: an unbounded window in which the
  signed, released catalog contradicts the admitted catalog on `main`.
- The admission pipeline's rigor (verify-first re-pin, fail-closed admission)
  is spent producing a state most careful consumers never see.

**Risk Assessment**:

- **Technical Risk**: High. Verification-disciplined consumers install from a
  stale catalog indefinitely.
- **Schedule Risk**: None to build; permanent operational tax.
- **Ecosystem Risk**: Medium. The marketplace advertises attested freshness it
  does not deliver.

### Option 2: Hub-driven release dispatch (rejected)

**Description**: Extend the catalog-update hub (or the `catalog` App) to fire a
`workflow_dispatch`/`repository_dispatch` release in the target marketplace
after its re-pin PR merges.

**Advantages**:

- Single central place to reason about the whole update→release chain.

**Disadvantages**:

- The hub does not observe the merge: its PRs auto-merge asynchronously under
  the target's `catalog-admission` gate, deliberately outside the hub's control
  (ADR-010's least-privilege driver: the merge control lives in the target).
  The hub would have to poll or subscribe to another repo's merge events.
- Misses human-authored catalog changes entirely — a maintainer editing
  `marketplace.json` directly gets no release, so the gap only half-closes.
- Widens the hub credential: the `catalog` App would need to drive release
  workflows in target repos, coupling catalog-write identity to release
  identity across repos.

**Risk Assessment**:

- **Technical Risk**: Medium-high. Event plumbing across repos for a merge the
  hub was designed not to own; silent no-release for human edits.
- **Schedule Risk**: Medium. Cross-repo dispatch, polling, or webhook surface
  to build and secure.
- **Ecosystem Risk**: Medium. Credential-scope creep on the `catalog` App.

### Option 3: Release directly from push-to-main (rejected)

**Description**: Add a `push: main` (path-filtered) trigger to the
marketplace's `release.yml` itself, computing a version in-run and creating the
tag as a by-product (or publishing untagged).

**Advantages**:

- No new workflow; one file owns the whole release story.

**Disadvantages**:

- Breaks the pipeline's stated invariant that publish is tag-gated ("a tag
  publishes nothing unattested" presumes the tag *precedes* the run). The
  `meta` job derives the version from `GITHUB_REF`; a branch-push run would
  need a forked version path and a publish gate rewritten around a ref that
  does not exist yet.
- The immutable anchor inverts: today a release is answerable to the tag that
  triggered it; here the tag would be a side effect of the run, so "what commit
  is release X" is answered by the run log, not the ref.

**Risk Assessment**:

- **Technical Risk**: Medium. Rewrites the proven pipeline's trigger semantics
  and version derivation rather than composing with them.
- **Schedule Risk**: Medium. `release.yml` is the org's attested-delivery
  exemplar; restructuring it is costlier than adding a seam beside it.
- **Ecosystem Risk**: Low-medium. Divergence from the org-wide tag-triggered
  release idiom every other repo follows.

### Option 4: Target-repo auto-tag seam via a reusable workflow (chosen)

**Description**: A new reusable workflow in `.github`
(`reusable-marketplace-release.yml`) that each marketplace calls through a thin
SHA-pinned caller triggered on `push` to `main`, path-filtered to the catalog
file. The reusable computes the next patch version from the repo's latest
`v*.*.*` tag, skips if the head commit is already tagged, mints a
release-App token, and pushes the annotated tag. The existing tag-gated
`release.yml` then runs unchanged.

**Advantages**:

- The trigger seam is the only new code; the attested release pipeline is
  reused byte-for-byte, tag-first, invariant intact.
- Covers both write paths — hub re-pins *and* human catalog edits — because it
  keys on the merged state, not on who produced it.
- Structurally recursion-proof: listens on branch pushes, writes only a tag
  ref; `release.yml` listens on tag pushes, pushes nothing.
- One reusable serves every marketplace, per the ADR-002 architecture.

**Disadvantages**:

- One more workflow seam to operate, and one more consumer of the `release`
  App's `contents: write`.
- Automated bumps are patch-only; the semantic weight of a change (a newly
  admitted plugin, say) is not reflected in the version unless a human
  intervenes.

**Risk Assessment**:

- **Technical Risk**: Low. Compose-only; each half is already proven in
  production, and the seam is a tag push.
- **Schedule Risk**: Low. One reusable plus a thin caller per marketplace.
- **Ecosystem Risk**: Low. Extends the org's existing reusable-caller idiom
  and the ADR-011 App fleet as designed.

## Decision

The org adopts Option 4: an auto-tag release seam in the marketplace repo,
implemented once as a reusable workflow in `.github`.

**Reusable (`.github/workflows/reusable-marketplace-release.yml`).** A
`workflow_call` reusable with inputs `catalog-path` (default
`.claude-plugin/marketplace.json`), `bump` (`patch` | `minor` | `major`,
default `patch`), and `dry-run` (boolean, default `false`); and one secret,
`app-private-key`, the org `release` App's private key (its client id is read
from `vars.RELEASE_CLIENT_APP_ID`, following the same convention as
`reusable-dependabot-automerge.yml`). Its single job:

1. Checks out the calling repo with full tag history.
2. Resolves the latest `v*.*.*` tag by semver order (`v0.0.0` when none) and
   computes the next version per `bump`.
3. **Skips successfully** if the head commit already carries a `v*.*.*` tag —
   idempotent under re-runs, and a human who tagged the merge commit first
   wins.
4. In `dry-run`, prints the resolved current and next versions and stops.
5. Otherwise mints an installation token via the SHA-pinned
   `actions/create-github-app-token` (client id `vars.RELEASE_CLIENT_APP_ID`,
   the App scoped to the calling repo) and pushes an annotated tag
   `v<next>` on the head commit using that token.

The App token is load-bearing, not a convenience: a ref pushed with the run's
own ephemeral `GITHUB_TOKEN` does not trigger workflows, so the tag must be
pushed by the `release` App for the marketplace's `on: push: tags` release
pipeline to fire. The `release` App already holds `contents: write` org-wide
and already publishes these repos' releases (`auth/apps.json`), so no new
credential or permission is introduced — only a new consumer.

**Thin caller (each marketplace repo, `.github/workflows/marketplace-release.yml`).**

```yaml
"on":
  push:
    branches: [main]
    paths:
      - ".claude-plugin/marketplace.json"
  workflow_dispatch:
    inputs:
      bump:
        description: "Version component to bump"
        type: choice
        options: [patch, minor, major]
        default: patch
      dry-run:
        type: boolean
        default: false

concurrency:
  group: marketplace-release-${{ github.ref }}

permissions:
  contents: read

jobs:
  tag:
    uses: modeled-information-format/.github/.github/workflows/reusable-marketplace-release.yml@<sha>
    with:
      bump: ${{ inputs.bump || 'patch' }}
      dry-run: ${{ inputs.dry-run || false }}
    secrets:
      app-private-key: ${{ secrets.RELEASE_CLIENT_APP_PRIVATE_KEY }}
```

The push trigger is path-filtered to the catalog file, so docs-site and CI
changes on `main` release nothing. `workflow_dispatch` with the `bump` input is
the human path for minor/major bumps; manually pushed tags remain first-class
and, via the skip guard, take precedence on the same commit.

**End-to-end flow after this decision.** Plugin repo cuts an attested release →
hub re-pins the catalog verify-first and opens an auto-merge PR (ADR-010) →
`catalog-admission` re-verifies fail-closed and the PR merges → the caller
fires on the catalog-path push to `main`, and the reusable tags `v<next>` as
the `release` App → the tag fires the marketplace's existing `release.yml`:
build → provenance → SBOM → seam verdicts → cosign-signed catalog → VEX →
fail-closed verify → publish (ADR-005). The pipeline that previously stopped at
the merge now terminates at a published, attested marketplace release embedding
the admitted catalog.

**Version semantics.** The marketplace's version identity remains the git tag;
`marketplace.json` carries no version field and the automation writes nothing
back to the repository. The catalog version is a monotonic snapshot counter in
semver form: automation always bumps patch; minor and major are reserved for
human judgments (a new plugin family, a structural catalog change) expressed
through the dispatch `bump` input or a manual tag.

**Rollout.** `claude-code-plugins` first, `gdlc` (the org's second marketplace,
same admission-gate pattern) immediately after, each as a thin caller of the
same reusable.

## Consequences

### Positive

1. **Bounded staleness**: the released, signed catalog tracks the admitted
   catalog at pipeline latency. Release cadence equals admission cadence, with
   the weekly hub schedule (ADR-010) as its routine upper bound.
2. **Pipeline reuse**: the attested release path — provenance, SBOM, gate
   verdicts, signed catalog, fail-closed verify, tag-gated publish — is
   exercised unchanged; this decision adds a trigger, not a pipeline.
3. **Both write paths covered**: hub re-pins and human catalog edits release
   identically, because the seam keys on the merged catalog state.
4. **One mechanism, every marketplace**: a single reusable serves
   `claude-code-plugins` and `gdlc`, and any future marketplace opts in with a
   thin caller.

### Negative

1. **Release volume grows**: every admitted catalog change publishes a release.
   At the hub's weekly cadence this is modest, but a busy week produces several
   releases, each with full attestation cost (CI minutes, Rekor entries,
   release-list noise).
2. **Patch-only automation under-communicates**: a semantically significant
   catalog change (a newly admitted plugin) lands as a patch bump unless a
   human pre-empts with the dispatch input or a manual tag.
3. **Wider routine exercise of the `release` App**: its `contents: write` is
   now invoked on every admitted catalog change, not only at human-initiated
   releases — more audit-log surface for the same credential.

### Neutral

1. **The tag stays the version identity**: no version field is added to
   `marketplace.json`. Stamping one was rejected because the write-back would
   need a commit to a protected `main` and would land inside the automation's
   own path filter — a PR-per-release loop for no verification gain (the
   released catalog is already cosign-signed and digest-bound).
2. **Automated tags are attributable**: tags minted by the seam are annotated
   and authored by the `release` App identity, distinguishable in the audit
   log from human tags.
3. **Admission remains the merge control**: this decision starts *after* the
   merge; it neither weakens nor duplicates the `catalog-admission` gate,
   which continues to run on every PR and push to `main` (ADR-010).
4. **The catalog-update machinery is untouched**: the hub workflow, the
   composite engine (`.github/actions/plugin-catalog-update/`), and the
   deny-list (`catalog-update/deny-list.yaml`) need no code change — the seam
   composes after their terminal step. Only `catalog-update/README.md`'s flow
   narrative gains the post-merge release step (Implementation item 7).

## Decision Outcome

An admitted catalog state can no longer silently diverge from the released one:
the seam converts every catalog change on `main` into a tag, and the tag into a
full attested release, closing the gap between ADR-010's admission pipeline and
ADR-005's release pipeline with a single compose-only trigger.

Mitigations for the accepted negatives: release noise is bounded by the
path filter (only catalog changes release) and the hub's weekly cadence, and
the `dry-run` input gives a no-write rehearsal path; the patch-only semantic
flattening is escapable at any time via the dispatch `bump` input or a manual
tag, which the skip guard lets win; the `release` App's added consumer is
declared in `auth/apps.json` (jq-validated in CI per ADR-011), keeping the
credential's consumer set auditable.

### Implementation

Work items, in order; each is verifiable as stated.

1. **Add the reusable** `.github/workflows/reusable-marketplace-release.yml`
   with the inputs, secret, skip guard, dry-run, and App-token tag push
   specified in the Decision. Every action SHA-pinned; `pin-check` and
   `actionlint` must pass.
2. **Register it in the workflow catalog**
   (`.github/skills/attested-delivery/references/workflow-catalog.md`) — the
   `catalog-check` gate hard-fails the PR otherwise (ADR-010).
3. **Declare the new consumer** in `auth/apps.json` under the `release` App
   (`consumers` gains the reusable's path and each caller's path);
   `app-manifest-validate.yml` enforces this.
4. **Add the thin caller** to `claude-code-plugins` as
   `.github/workflows/marketplace-release.yml` (snippet in the Decision),
   pinning the reusable to a full-length SHA.
5. **Verify end-to-end on `claude-code-plugins`**: first a `workflow_dispatch`
   dry-run (resolved versions printed, nothing pushed); then a live catalog
   change merged through admission, observing the auto-tag (`v0.1.1` from the
   current `v0.1.0`), the release run, and finally
   `gh attestation verify` on the released tarball plus `cosign verify-blob`
   on the released catalog — both must pass fail-closed.
6. **Repeat the caller for `gdlc`**, and update `auth/apps.json` consumers
   accordingly.
7. **Documentation**: extend `catalog-update/README.md`'s per-entry flow
   narrative with the post-merge release step; note the seam in the release
   runbook (`docs/runbooks/release-runbook.md`); this ADR and the amended
   ADR-010 land together with the index update.

## Related Decisions

- [ADR-005: Artifact Signing, SLSA Attestation & Fail-Closed Verification](ADR-005-signing-attestation-verification.md) -- the attested release pipeline this seam triggers; its tag-gated publish invariant is preserved by tagging first.
- [ADR-010: Plugin Catalog Hub and Manifest Review](ADR-010-plugin-catalog-hub.md) -- the admission pipeline this decision extends; its terminal step (the admission-verified merge) becomes this seam's starting point.
- [ADR-011: Least-Privilege App Fleet](ADR-011-least-privilege-app-fleet.md) -- supplies the `release` App identity that mints the tag; this decision adds a consumer to an existing credential rather than a new credential.

## Links

- [Attested catalog-updater README](https://github.com/modeled-information-format/.github/blob/main/catalog-update/README.md) -- the update→admission flow whose terminal step this ADR extends.
- [SLSA Build Provenance specification](https://slsa.dev/provenance/v1) -- the provenance predicate the triggered release attests and the admission gate verifies.
- [GitHub Actions: triggering a workflow from a workflow](https://docs.github.com/en/actions/using-workflows/triggering-a-workflow#triggering-a-workflow-from-a-workflow) -- the `GITHUB_TOKEN` event-suppression rule that makes the App-minted tag push load-bearing.

## More Information

- **Date:** 2026-07-05
- **Source:** `claude-code-plugins/.github/workflows/release.yml`,
  `claude-code-plugins/.github/workflows/catalog-admission.yml`,
  `.github/workflows/plugin-catalog-update-hub.yml`, `auth/apps.json`,
  `catalog-update/README.md`.
- **Related ADRs:** ADR-005, ADR-010, ADR-011

## Audit

### 2026-07-05

**Status:** Pending

**Findings:**

| Finding | Files | Lines | Assessment |
|---------|-------|-------|------------|
| Marketplace release pipeline triggers only on `v*.*.*` tag push or `workflow_dispatch`; no push-to-main trigger exists | `claude-code-plugins/.github/workflows/release.yml` | L19-L23 | compliant (pre-decision state confirmed) |
| Publish is tag-gated and mints the `release` App token (`RELEASE_CLIENT_APP_ID`/`RELEASE_CLIENT_APP_PRIVATE_KEY`) | `claude-code-plugins/.github/workflows/release.yml` | L340, L367-L372 | compliant |
| `catalog-admission` runs on every `pull_request` and `push` to `main` — the seam starts strictly after this gate | `claude-code-plugins/.github/workflows/catalog-admission.yml` | L24-L26 | compliant |
| `release` App holds `contents: write` org-wide (`install_on: all`); tag creation needs no new permission | `auth/apps.json` | L71-L90 | compliant |
| Hub mints the `catalog` App (`CATALOG_CLIENT_APP_ID`) and its flow ends at the auto-merge PR; no release dispatch exists | `.github/workflows/plugin-catalog-update-hub.yml` | L48-L49, L113-L114 | compliant (gap confirmed) |
| The documented per-entry update flow terminates at step 5 (auto-merge PR) with the target's `catalog-admission` gate as merge control; no post-merge step follows | `catalog-update/README.md` | L37-L50 | compliant (gap confirmed) |
| `marketplace.json` carries no version field; version identity is the git tag (latest: `v0.1.0`) | `claude-code-plugins/.claude-plugin/marketplace.json` | — | compliant |
| `reusable-marketplace-release.yml` exists with skip guard, dry-run, and App-token tag push | `.github/workflows/reusable-marketplace-release.yml` | — | pending |
| Workflow catalog lists the new reusable | `.github/skills/attested-delivery/references/workflow-catalog.md` | — | pending |
| `auth/apps.json` `release.consumers` includes the reusable and each caller | `auth/apps.json` | — | pending |
| Thin callers live in `claude-code-plugins` and `gdlc` | `<marketplace>/.github/workflows/marketplace-release.yml` | — | pending |
| End-to-end verified: admitted catalog change → auto tag → attested release; `gh attestation verify` + `cosign verify-blob` pass | release run evidence | — | pending |

**Summary:** The pre-decision state is confirmed in code: admission ends at the
merge, release starts at a human tag, and nothing connects them. The decision's
mechanism rows are pending implementation; work items 1-7 in the Implementation
section map one-to-one onto the pending rows.

**Action Required:** Implement work items 1-7; re-audit to Compliant when the
end-to-end row passes.
