---
title: "Least-Privilege App Fleet and Org-Wide Standard Gate Suite"
description: "Supersedes ADR-008: five least-privilege Apps (ci, catalog, pages, automerge, release) installed org-wide, minted via the OAuth client-id under one <ROLE>_CLIENT_APP_ID/_PRIVATE_KEY scheme in a jq-gated apps.json. Every org repo standardizes on the full gate suite authenticated by these apps."
type: adr
conceptType: semantic
x-ontology:
  id: mif-docs
  version: "1.0.0"
  entity_type: decision-record
category: process
tags:
  - github-app
  - identity
  - least-privilege
  - ci
  - tokens
  - security
status: accepted
created: 2026-06-30
updated: 2026-06-30
author: MIF Maintainers
project: modeled-information-format
technologies:
  - github-actions
  - github-app
  - oidc
  - jq
audience:
  - developers
  - architects
  - maintainers
related:
  - ADR-008-github-app-ci-identity.md
  - ADR-007-scorecard-posture.md
  - ADR-010-plugin-catalog-hub.md
  - ADR-013-marketplace-release-automation.md
---

# ADR-011: Least-Privilege App Fleet and Org-Wide Standard Gate Suite

## Status

Accepted — supersedes [ADR-008](ADR-008-github-app-ci-identity.md).

## Context

### Background and Problem Statement

ADR-008 established a single token-minting GitHub App, `modeled-information-format-ci`,
that every org workflow authenticates as. In practice the org grew two
inconsistently named references to that one identity and never provisioned one of
them: workflows read `vars.MIF_CI_CLIENT_APP_ID` / `secrets.MIF_CI_CLIENT_APP_PRIVATE_KEY`
for scorecard, dependabot-automerge, and the cross-repo Pages notify, while the
catalog hub reads `CATALOG_UPDATER_APP_CLIENT_ID` / `..._PRIVATE_KEY`. The
`MIF_CI_CLIENT_APP_PRIVATE_KEY` org secret was never created, so the Pages-notify
job (and every dependabot-automerge and scorecard caller) mints an empty key and
fails.

Beyond the missing secret, a single broad identity is used for narrow jobs:
auto-merging Dependabot PRs, writing the org Pages repo, and publishing releases
all run as the same App that also reads branch protection. A leak or misuse of one
key is a leak of all that authority.

### Current Limitations Before This Decision

- One App key authorizes unrelated jobs (scorecard reads, Pages writes,
  auto-merge, release publish) — no blast-radius isolation.
- Two naming schemes for one identity, plus a never-provisioned secret, so the
  failure is silent until a job needs the missing key.
- No single source of truth for which App exists, what it may do, where it is
  installed, and which workflow consumes it — the wiring is scattered across
  workflow files and prose.
- Token minting passed the numeric `app-id` value through the `client-id:` input;
  GitHub now emits a "Use client-id instead" deprecation warning and ties future
  features to the client-id.

## Decision Drivers

### Primary Decision Drivers

1. **Least privilege, blast-radius isolation**: Each job's identity must hold only
   the permissions that job needs, so a single key compromise cannot exercise
   unrelated authority.
2. **One consistent, drift-proof naming scheme**: Credentials must follow a single
   pattern keyed to the App's role, enforced automatically so names cannot diverge
   again.
3. **Single source of truth**: One manifest must declare every App, its
   permissions, its install scope, and its consuming workflows, validated in CI.
4. **Current GitHub best practice**: Minting must use the App OAuth `client-id`,
   not the deprecated `app-id`.
5. **Uniform org-wide posture**: Every repo must run the same reusable gate suite
   on the same shared identities, so security and governance coverage does not
   depend on per-repo wiring that drifts or is forgotten.

### Secondary Decision Drivers

1. **No new supply-chain surface**: The refactor must not add Actions allow-list
   or SHA-pin obligations beyond the already-pinned mint action.
2. **Signing identity stays separate**: Release publishing may use an App token,
   but SLSA keyless attestation must remain the run's ephemeral `GITHUB_TOKEN` +
   OIDC, unchanged (per ADR-005/ADR-008).
3. **Lean validation**: The CI gate must use tooling already on the runner (`jq`),
   not a new language/dependency stack.

## Considered Options

### Option 1: Keep the single CI App (status quo, ADR-008)

**Description**: Provision the missing `MIF_CI_CLIENT_APP_PRIVATE_KEY` secret and
leave one broad App for all jobs.

**Advantages**:

- Smallest change; one App, one key to manage.

**Disadvantages**:

- One key authorizes auto-merge, Pages writes, release publish, and posture reads
  alike — no isolation.
- Leaves the two-name inconsistency and offers no source of truth or drift guard.

**Risk Assessment**:

- **Technical Risk**: Medium. Works, but a single broad credential is a standing
  blast-radius and the naming drift recurs.
- **Schedule Risk**: Low.
- **Ecosystem Risk**: Medium. Still mints via the value the deprecation warning
  targets unless separately fixed.

### Option 2: Five least-privilege Apps + central manifest + jq gate (chosen)

**Description**: Split into `ci`, `catalog`, `pages`, `automerge`, and `release`
Apps, each with a minimal permission set and scoped installs. Credentials follow
`<ROLE>_CLIENT_APP_ID` (org variable, the OAuth client-id) and
`<ROLE>_CLIENT_APP_PRIVATE_KEY` (org secret). `auth/apps.json` is the single source
of truth; `app-manifest-validate.yml` validates it with `jq` (SHA-pin, role/name
consistency, uniqueness). Minting stays inline via SHA-pinned
`actions/create-github-app-token` using `client-id:`.

**Advantages**:

- Blast-radius isolation: each key holds only its job's authority.
- One enforced naming scheme; the gate fails if a name drifts from its role.
- A declarative manifest documents and tests the whole fleet.
- Uses the client-id (current best practice) and only the already-pinned mint
  action — no new supply-chain surface.

**Disadvantages**:

- Five Apps, five variables, five secrets to provision and rotate instead of one.

**Risk Assessment**:

- **Technical Risk**: Low. Least-privilege, short-lived tokens; the manifest gate
  prevents silent drift.
- **Schedule Risk**: Medium. Requires creating five Apps and provisioning ten
  credentials before the workflows go green.
- **Ecosystem Risk**: Low. Standard App installs; client-id minting is the
  supported path.

### Option 3: Split Apps but mint through a shared composite action

**Description**: Same five Apps, but route every mint through a shared
`actions/mint-app-token` composite to DRY the minting step.

**Advantages**:

- One place to change the mint action SHA or inputs.

**Disadvantages**:

- A reusable *workflow* runs in the **caller's** checkout, so it cannot reference
  `.github`'s local `./actions/mint-app-token`; only a cross-repo
  `modeled-information-format/.github/actions/...@<sha>` would resolve, which adds
  an Actions allow-list entry and a SHA-pin to maintain in every consuming repo.
- That buys no safety: an inline `create-github-app-token` step already keeps the
  minted token inside the job. The composite adds surface for no isolation gain.

**Risk Assessment**:

- **Technical Risk**: Medium. New cross-repo action dependency to pin and
  allow-list, for a purely cosmetic DRY.
- **Schedule Risk**: Low.
- **Ecosystem Risk**: Medium. Composite actions that wrap pinned actions are
  permitted, but they widen the allow-list the org keeps deliberately narrow.

## Decision

Split the single CI identity into **five least-privilege GitHub Apps** — `ci`,
`catalog`, `pages`, `automerge`, `release` — declared in **`auth/apps.json`**, the
single source of truth. Each App is identified by its **OAuth client-id** (the
deprecated `app-id` is retired) carried in an org **variable**
`<ROLE>_CLIENT_APP_ID`; its private key is an org **secret**
`<ROLE>_CLIENT_APP_PRIVATE_KEY`. The variable is a public identifier, so
optional-App jobs continue to gate on it in `if:` and fall back to `GITHUB_TOKEN`.

Workflows mint short-lived installation tokens **inline** via SHA-pinned
`actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1` (v3.2.0)
using the `client-id:` input. There is **no composite** mint action: a reusable
workflow runs in the caller's checkout and cannot use `.github`'s local composite,
and a cross-repo composite would add allow-list/pin surface for no safety gain over
an inline pinned mint (Option 3).

`auth/apps.json` is validated in CI by **`app-manifest-validate.yml`** using `jq`
(pre-installed on the runner): the mint action is SHA-pinned, each app's
`id_variable`/`key_secret` equals `<ROLE>_CLIENT_APP_ID`/`_PRIVATE_KEY` for its own
key, and no two apps share a credential. `auth/apps.schema.json` is the declarative
contract referenced from the manifest's `$schema` for editor-time validation.

Per-App permission sets are the minimum each consumer needs:

| App | Repository permissions | Primary consumer |
| --- | --- | --- |
| `ci` | contents:read, administration:read, pull_requests:read, issues:read, actions:read, checks:read | OpenSSF Scorecard |
| `catalog` | contents:write, actions:write, pull_requests:write | plugin-catalog-update-hub |
| `pages` | contents:write, pages:write, actions:write | org Pages deploy/notify |
| `automerge` | contents:write, pull_requests:write | dependabot auto-merge |
| `release` | contents:write, packages:write | release.yml publish/contents |

`release.yml` moves **only** its `gh release` / contents-write authentication to the
`release` App. Its `id-token: write` + `attestations: write` keyless OIDC
attestation is unchanged, so the attestation signer SAN stays the workflow and
`gh attestation verify` is unaffected (consistent with ADR-005/ADR-008's separation
of signing from the automation identity).

**Org-wide standardization.** Every org repo adopts the full reusable gate suite —
`quality-gates`, `scorecard`, `dependabot-automerge`, `label-sync`, the SAST/SCA
gates, `dast`, `release`, and `deploy` where applicable — authenticated by these
five apps. The apps are **installed org-wide** (`auth/apps.json` `install_on: all`)
and each workflow mints only the apps its gates use. Repos are brought onto the
standard suite under epic #37; the apps exist precisely because the suite runs
everywhere, not on a hand-picked subset. The mint pattern (ADR-002's reusable
gate architecture) extends ADR-002 from "the gates that exist are reusable" to
"every repo runs them on shared least-privilege identities."

## Consequences

### Positive

1. **Blast-radius isolation**: A compromised key exercises only its App's narrow
   permissions, not the whole automation surface.
2. **Drift-proof naming**: The jq gate fails the build if any App's variable or
   secret diverges from `<ROLE>_CLIENT_APP_*`, so the two-name regression cannot
   recur.
3. **Single source of truth**: `auth/apps.json` documents and tests the fleet —
   permissions, installs, consumers — in one validated file.
4. **Current best practice, no new surface**: Minting uses the client-id and only
   the already-pinned mint action; no composite, no new allow-list entries.
5. **Signing stays keyless and separate**: SLSA attestation is untouched.
6. **Uniform posture**: Every repo runs the same gates on the same identities, so
   coverage no longer depends on per-repo wiring being remembered.

### Negative

1. **More credentials to provision and rotate**: Five Apps, five variables, five
   secrets instead of one App and one key.
2. **Staged cutover**: The workflows fail until all five Apps exist and their
   credentials are provisioned; the change lands as draft PRs that go green on
   provisioning.
3. **Onboarding cost**: Thin repos (mnemonic, structured-madr, ...) need net-new
   caller workflows wired to their own toolchain to reach the standard suite; this
   is tracked per-repo under epic #37.

### Neutral

1. **Manifest is documentation, not runtime**: `auth/apps.json` is the source of
   truth and CI gate, but nothing reads it at mint time — each workflow still names
   its own variable/secret. The gate keeps the two in agreement.
2. **Install scope is org-wide**: Every App is installed on all org repos
   (`install_on: all`); each workflow mints only the Apps its gates use, so adding a
   consumer is just wiring the workflow, not a new install.

## Decision Outcome

The org runs five least-privilege Apps minted inline via the client-id, with
`auth/apps.json` as the validated source of truth. ADR-008's single-identity
decision is superseded; its rationale for App-over-PAT, short-lived tokens, and
keyless-signing separation carries forward unchanged — only the count, naming, and
manifest are new.

### Implementation

**Inline mint (per consuming workflow), e.g. scorecard:**

```yaml
- name: Mint ci App token
  id: app
  if: ${{ vars.CI_CLIENT_APP_ID != '' }}
  continue-on-error: true
  uses: actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1 # v3.2.0
  with:
    client-id: ${{ vars.CI_CLIENT_APP_ID }}
    private-key: ${{ secrets.app-private-key }}
    owner: ${{ github.repository_owner }}
    repositories: ${{ github.event.repository.name }}
```

**Manifest gate (`jq`, runner-preinstalled):** `app-manifest-validate.yml` checks
the SHA pin, the `<ROLE>_CLIENT_APP_*` role/name match, and credential uniqueness
on every PR/push touching `auth/**`.

**Provisioning (maintainer):** create the five Apps, then set each
`<ROLE>_CLIENT_APP_ID` org variable (the App's OAuth client-id) and
`<ROLE>_CLIENT_APP_PRIVATE_KEY` org secret, both visibility `all`. Install each App
on the repos in its `install_on` list.

## Related Decisions

- [ADR-008: GitHub App CI Identity](ADR-008-github-app-ci-identity.md) -- superseded by this ADR; the single `modeled-information-format-ci` identity becomes the five-App fleet, and its App-over-PAT / short-lived-token / separate-signing rationale carries forward.
- [ADR-007: OpenSSF Scorecard Posture](ADR-007-scorecard-posture.md) -- the scorecard reusable consumes the `ci` App (renamed from `MIF_CI_CLIENT_APP_ID`).
- [ADR-010: Plugin Catalog Hub](ADR-010-plugin-catalog-hub.md) -- the catalog hub consumes the `catalog` App (renamed from `CATALOG_UPDATER_APP_*`).
- [ADR-005: Artifact Signing & Attestation](ADR-005-signing-attestation-verification.md) -- release publishing uses the `release` App token, but attestation stays keyless via the run's OIDC, unaffected.
- [ADR-013: Automated Attested Marketplace Release on Catalog Admission](ADR-013-marketplace-release-automation.md) -- adds a consumer to the `release` App: a reusable auto-tag workflow pushes the marketplace's next version tag with a release-App token so the tag push fires the release pipeline; no new credential or permission, only a new `consumers` entry in `auth/apps.json`.

## Links

- [actions/create-github-app-token](https://github.com/actions/create-github-app-token) -- mints installation tokens; recommends `client-id` (the `app-id` input is deprecated).
- [GitHub Apps can now use the client ID to fetch installation tokens](https://github.blog/changelog/2024-05-01-github-apps-can-now-use-the-client-id-to-fetch-installation-tokens/) -- the changelog establishing client-id as the forward path.
- [auth/apps.json](../../auth/apps.json) -- the manifest this ADR governs.

## More Information

- **Date:** 2026-06-30
- **Source:** `auth/apps.json`, `auth/apps.schema.json`, `.github/workflows/app-manifest-validate.yml`, `.github/workflows/reusable-scorecard.yml`, `.github/workflows/reusable-dependabot-automerge.yml`, `.github/workflows/plugin-catalog-update-hub.yml`.
- **Supersedes:** ADR-008.

## Audit

### 2026-06-30

**Status:** Compliant

**Findings:**

| Finding | Files | Lines | Assessment |
|---------|-------|-------|------------|
| Five least-privilege apps declared with per-role permissions, installs, and consumers | `auth/apps.json` | apps.* | compliant |
| Naming scheme `<ROLE>_CLIENT_APP_ID` / `_PRIVATE_KEY` enforced by the jq gate (role match, uniqueness, SHA pin) | `.github/workflows/app-manifest-validate.yml` | run step | compliant |
| Scorecard mints the `ci` App via client-id, gated on the public variable, fail-soft | `.github/workflows/reusable-scorecard.yml` | L75-L82 | compliant |
| Dependabot auto-merge mints the `automerge` App via client-id | `.github/workflows/reusable-dependabot-automerge.yml` | L53-L57 | compliant |
| Catalog hub mints the `catalog` App via client-id + private key | `.github/workflows/plugin-catalog-update-hub.yml` | L46-L50, L111-L116 | compliant |
| Provisioning is pending the maintainer creating the five Apps and setting the ten credentials | (org settings) | — | pending |

**Summary:** The single `modeled-information-format-ci` identity is replaced by
five least-privilege Apps — `ci`, `catalog`, `pages`, `automerge`, `release` —
minted inline via SHA-pinned `actions/create-github-app-token` using the OAuth
client-id, with `auth/apps.json` as the jq-validated source of truth. No composite
mint action is introduced; keyless OIDC attestation is unchanged.

**Action Required:** Create the five Apps and provision each `<ROLE>_CLIENT_APP_ID`
variable + `<ROLE>_CLIENT_APP_PRIVATE_KEY` secret (visibility `all`); the draft PRs
go green once provisioning completes.
