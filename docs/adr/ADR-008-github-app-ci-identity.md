---
title: "GitHub App CI Identity (Token-Minting App vs PAT)"
description: "Org workflows authenticate as a dedicated GitHub App (modeled-information-format-ci) by minting short-lived installation tokens via SHA-pinned actions/create-github-app-token, reading the App client id from vars.MIF_CI_CLIENT_APP_ID and the private key from an org secret — chosen over a personal access token for scoped, rotating, auditable, repo-narrowed identity. The App is a token-minting identity (hook active:false), not webhook-driven; artifact signing instead uses the run's ephemeral GITHUB_TOKEN + OIDC id-token (SLSA L3)."
type: adr
category: process
tags:
  - github-app
  - identity
  - ci
  - tokens
  - security
  - oidc
status: accepted
created: 2026-06-29
updated: 2026-06-29
author: MIF Maintainers
project: modeled-information-format
technologies:
  - github-actions
  - github-app
  - oidc
  - slsa
audience:
  - developers
  - architects
  - maintainers
related:
  - ADR-002-reusable-quality-gate-architecture.md
  - ADR-009-branch-protection-standardization.md
---

# ADR-008: GitHub App CI Identity (Token-Minting App vs PAT)

## Status

Accepted

## Context

### Background and Problem Statement

Org automation in `modeled-information-format` needs a write-capable identity for
work the run's default `GITHUB_TOKEN` cannot do: cross-repo dispatch, repo
provisioning, enumerating installation repositories, and reading branch
protection (`administration:read`) so that posture checks score from real
settings rather than the partial view the default token sees. The default
`GITHUB_TOKEN` is scoped to a single repository and cannot read org-level or
sibling-repo state; relying on it alone caps several gates.

The naive alternative is a personal access token (PAT) stored as an org secret.
A PAT inherits a human owner's full account scope, does not expire on its own,
is not narrowed to specific repositories, and attributes automated actions to a
person rather than to a bot identity. The org needed a write identity that is
scoped, short-lived, auditable, and decoupled from any individual's account.

A separate but adjacent concern: artifact **signing** must not depend on this
identity at all. SLSA L3 build provenance requires the signer to be the run's
own ephemeral `GITHUB_TOKEN` + OIDC `id-token`, not a long-lived App or PAT
token. The identity decision must therefore keep the automation identity and the
signing identity distinct.

### Current Limitations Before This Decision

- The default `GITHUB_TOKEN` cannot read branch protection
  (`administration:read`) or enumerate installation repositories, so
  posture/discovery jobs were limited to what a single-repo token can see.
- A PAT-based identity would be account-scoped, non-expiring, un-narrowed to
  repositories, and attributed to a human owner — weak on least privilege,
  rotation, and auditability.
- No org-standard mechanism existed for workflows to obtain a scoped, short-lived
  write token on demand.

## Decision Drivers

### Primary Decision Drivers

1. **Least privilege, per-repo scoping**: The automation identity must grant only
   the permissions it needs and be narrowable to specific repositories per run,
   not a blanket account scope.
2. **Short-lived, rotating credentials**: Tokens used in CI must expire on their
   own. A minted installation token lives for the run; a PAT persists until
   manually revoked.
3. **Auditable, non-human identity**: Automated writes must attribute to a
   dedicated bot identity (the App), not to an individual's account, so the audit
   trail is unambiguous.
4. **Signing identity stays separate**: The automation identity must not be the
   signing identity. SLSA L3 provenance is keyless via the run's ephemeral
   `GITHUB_TOKEN` + OIDC, independent of this App.

### Secondary Decision Drivers

1. **SHA-pinned, allow-listed supply chain**: The token-minting action must be a
   full 40-character SHA pin and must clear the org Actions allow-list, the same
   posture every `uses:` reference is held to.
2. **Fail-soft gating where the App is optional**: Where an App token only
   enriches a check (e.g. branch-protection reads), the workflow must degrade to
   `GITHUB_TOKEN` when no key is configured rather than fail hard. Because secrets
   cannot be referenced in `if:`, the gate keys on the public client-id variable.
3. **Reproducible, non-manual provisioning**: Creating the App must be repeatable
   from committed source (the manifest flow), with the private key held outside
   any repo.

## Considered Options

### Option 1: Personal access token (PAT) stored as an org secret

**Description**: Mint a classic or fine-grained PAT owned by a maintainer (or a
machine user) and store it as an org secret for workflows to consume.

**Advantages**:

- Simplest to set up; one secret, no App installation.

**Disadvantages**:

- Account-scoped: inherits the owner's full reach rather than a narrowed
  permission set.
- Non-expiring by default; rotation is manual and easy to neglect.
- Not narrowable to specific repositories per run.
- Attributes automated actions to a human (or a machine user that itself needs
  managing), weakening the audit trail.

**Risk Assessment**:

- **Technical Risk**: High. A leaked PAT exposes broad, long-lived access; weak
  on least privilege and rotation.

### Option 2: Default `GITHUB_TOKEN` only

**Description**: Use only the per-run `GITHUB_TOKEN`, adding no extra identity.

**Advantages**:

- Zero additional configuration; the token is ephemeral and run-scoped by design.

**Disadvantages**:

- Cannot read branch protection (`administration:read`) or org-level state, so
  posture checks score from incomplete data.
- Single-repo scope; cannot enumerate installation repositories or dispatch
  cross-repo work.

**Risk Assessment**:

- **Technical Risk**: Medium. Safe but insufficient — several required jobs
  cannot function with it alone.

### Option 3: Dedicated GitHub App minting short-lived installation tokens (chosen)

**Description**: Create a dedicated GitHub App, `modeled-information-format-ci`,
with a narrow default permission set, installed org-wide. Workflows mint a
short-lived installation token at run time via SHA-pinned
`actions/create-github-app-token`, reading the App client id from an org variable
(`vars.MIF_CI_CLIENT_APP_ID`) and the private key from an org secret. The App is a
token-minting identity only: its webhook is created inactive (`active:false`) and
never delivers. Artifact signing is explicitly **not** done with this App —
signing uses the run's ephemeral `GITHUB_TOKEN` + OIDC `id-token`.

**Advantages**:

- Tokens are short-lived (run-scoped) and can be narrowed to specific
  repositories via the action's `repositories` input.
- Permission set is declared narrowly on the App, independent of any human
  account.
- Automated writes attribute to a dedicated bot identity — clean audit trail.
- Client id is a public identifier carried in an org *variable*; only the private
  key is a secret, so optional-App jobs can gate on the variable in `if:`.
- Keeps the signing identity separate, preserving SLSA L3 keyless provenance.

**Disadvantages**:

- More moving parts: App creation via the manifest flow, an org variable, an org
  secret, and private-key custody outside any repo.
- The token-minting action becomes a supply-chain dependency that must be
  SHA-pinned and allow-listed.

**Risk Assessment**:

- **Technical Risk**: Low. Least-privilege, short-lived tokens with a clean audit
  trail; the private key is the single sensitive secret and lives outside the
  repos.

## Decision

Org workflows authenticate as the dedicated GitHub App
`modeled-information-format-ci`. At run time they mint a short-lived installation
token via `actions/create-github-app-token`, SHA-pinned at
`bcd2ba49218906704ab6c1aa796996da409d3eb1` (v3.2.0), passing the App **client
id** (read from `vars.MIF_CI_CLIENT_APP_ID`) and the App **private key** (read
from an org secret) — never a PAT.

The App is defined by a committed manifest and created via the GitHub App
manifest flow (there is no REST endpoint to create an App from scratch with a
PAT). The manifest declares `public: false`, a narrow `default_permissions` set
(`contents: write`, `metadata: read`, `pull_requests: write`, `issues: write`,
`actions: write`, `checks: write`, `attestations: write`, `administration: read`,
`members: read`), and `hook_attributes.active: false`. The inactive hook reflects
that this App is a **token-minting identity, not webhook-driven**; GitHub's
manifest flow requires a webhook URL, so one is supplied but never activated.

`actions/create-github-app-token` takes `client-id` (the older `app-id` input is
deprecated). The client id is a public identifier and is carried in an org
*variable*; the private key is the only secret. This split lets optional-App jobs
gate on the variable in `if:` (secrets cannot be used in `if:`) and fall back to
`GITHUB_TOKEN` when no key is configured.

Artifact **signing** is deliberately out of scope for this App. In-workflow
signing uses the run's own ephemeral `GITHUB_TOKEN` + OIDC `id-token`, which is
what SLSA L3 requires; the App is the automation/write identity only (repo
provisioning, cross-repo dispatch, branch-protection reads, installation-repo
enumeration).

## Consequences

### Positive

1. **Least privilege + short-lived tokens**: Each run mints a token scoped to a
   narrow permission set and (optionally) to specific repositories; the token
   expires with the run.
2. **Clean audit trail**: Automated writes attribute to the App, not to a human
   account.
3. **Fail-soft optional use**: Jobs that only benefit from the App (e.g.
   branch-protection reads) gate on the public client-id variable and degrade to
   `GITHUB_TOKEN` when no key is present.
4. **Signing stays keyless and separate**: SLSA L3 provenance remains keyless via
   the run's OIDC token, unaffected by this identity.

### Negative

1. **Provisioning complexity**: Requires the manifest flow, an org variable, an
   org secret, and private-key custody outside any repo — more setup than a single
   PAT secret.
2. **Supply-chain dependency**: `actions/create-github-app-token` must be
   SHA-pinned and allow-listed, and re-pinned when upgraded.

### Neutral

1. **Private-key rotation is a deliberate operation**: The App private key is the
   single sensitive secret; rotating it is a manual, owner-driven step (the right
   posture, but not automatic).
2. **Two distinct App consumers**: Different workflows read the App credentials
   under their own variable/secret names (e.g. `MIF_CI_CLIENT_APP_ID` for the
   scorecard reusable; `CATALOG_UPDATER_APP_CLIENT_ID`/`..._PRIVATE_KEY` for the
   catalog hub). The underlying App identity is the same.

## Decision Outcome

Org workflows hold no PAT. They mint short-lived `modeled-information-format-ci`
installation tokens on demand via SHA-pinned `actions/create-github-app-token`,
keyed on a public client-id variable plus a private-key secret. The App is a
narrow, non-webhook, token-minting identity; signing remains keyless via the
run's ephemeral `GITHUB_TOKEN` + OIDC.

### Implementation

**Token-minting step (within a reusable workflow):**

```yaml
- name: Mint CI App token
  id: app-token
  if: ${{ vars.MIF_CI_CLIENT_APP_ID != '' }}
  continue-on-error: true
  uses: actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1 # v3.2.0
  with:
    client-id: ${{ vars.MIF_CI_CLIENT_APP_ID }}
    private-key: ${{ secrets.app-private-key }}
    owner: ${{ github.repository_owner }}
    repositories: ${{ github.event.repository.name }}
```

**App creation (manifest flow):** Open `docs/onboarding/app/create-app.html` as
an org owner, submit the manifest (`docs/onboarding/app/manifest.json`), then
exchange the returned one-time `?code=` for the App id + private key:

```bash
gh api -X POST /app-manifests/<code>/conversions --jq '{id, slug, html_url}'
```

Save the `pem` to a location outside any repo (e.g.
`~/.secrets/modeled-information-format-ci.pem`); never commit it. Install the App
org-wide.

**Credential wiring:** Client id → org variable (`vars.MIF_CI_CLIENT_APP_ID`,
public identifier); private key → org secret (the key is the only sensitive
value).

**Action pin:** `actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1`
(v3.2.0), used by the workflows that need an App token.

## Related Decisions

- [ADR-002: Reusable Quality-Gate Architecture](ADR-002-reusable-quality-gate-architecture.md) -- the reusable workflows that consume the minted App token (e.g. the scorecard reusable reads branch protection with it) are defined under that architecture.
- [ADR-009: Branch-Protection Standardization](ADR-009-branch-protection-standardization.md) -- the App's `administration:read` permission is what lets posture checks score branch protection from real settings rather than the default token's partial view.

## Links

- [GitHub Apps documentation](https://docs.github.com/en/apps) -- the App identity model and installation tokens.
- [actions/create-github-app-token](https://github.com/actions/create-github-app-token) -- the action that mints short-lived installation tokens from the App client id + private key.
- [SLSA Build Provenance specification](https://slsa.dev/provenance/v1) -- the provenance level whose keyless signing requires the run's ephemeral token, not this App.

## More Information

- **Date:** 2026-06-29
- **Source:** `docs/onboarding/app/manifest.json`, `docs/onboarding/app/create-app.html`, `docs/onboarding/RUNBOOK.md`, `catalog-update/README.md`, `.github/workflows/reusable-scorecard.yml`, `.github/workflows/plugin-catalog-update-hub.yml`.
- **Related ADRs:** ADR-002, ADR-009

## Audit

### 2026-06-29

**Status:** Compliant

**Findings:**

| Finding | Files | Lines | Assessment |
|---------|-------|-------|------------|
| App `modeled-information-format-ci` declared `public: false` with a narrow `default_permissions` set (contents:write, metadata:read, pull_requests:write, issues:write, actions:write, checks:write, attestations:write, administration:read, members:read) | `docs/onboarding/app/manifest.json` | L2, L5, L17-L27 | compliant |
| App is a token-minting identity, not webhook-driven: `hook_attributes.active: false`; manifest description states it is NOT used for artifact signing | `docs/onboarding/app/manifest.json` | L4, L6-L9 | compliant |
| Manifest-flow rationale (no REST path to create an App with a PAT; webhook required but created inactive because the App is token-minting, not webhook-driven) | `docs/onboarding/app/create-app.html` | L2-L29, L48-L52 | compliant |
| App is the org automation/write identity (repo provisioning, cross-repo dispatch) and is explicitly NOT used for signing/GHCR — signing uses the run's ephemeral GITHUB_TOKEN + OIDC id-token (SLSA L3) | `docs/onboarding/RUNBOOK.md` | L20-L31 | compliant |
| Token minted via SHA-pinned `actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1` (v3.2.0), reading client id from `vars.MIF_CI_CLIENT_APP_ID` | `.github/workflows/reusable-scorecard.yml` | L75, L77, L79 | compliant |
| Private key passed as a workflow secret (`app-private-key`); the App installation token grants `administration:read` so Scorecard reads real branch protection vs the default GITHUB_TOKEN's partial view; gate keys on the public client-id var because secrets cannot be used in `if:`; fails soft to GITHUB_TOKEN | `.github/workflows/reusable-scorecard.yml` | L32-L41, L75-L82 | compliant |
| Same token-minting action and SHA pin reused by the catalog-update hub (consistent App-token pattern across workflows) | `.github/workflows/plugin-catalog-update-hub.yml` | L46, L111 | compliant |
| `actions/create-github-app-token` takes `client-id` (the `app-id` input is deprecated); client id is a public identifier kept in an org variable, private key in an org secret | `catalog-update/README.md` | L62-L65, L79-L83 | compliant |
| App id `4139655` | (not present in any opened grounding file) | — | pending |

**Summary:** Org workflows authenticate as the dedicated GitHub App
`modeled-information-format-ci` by minting short-lived installation tokens via
the SHA-pinned `actions/create-github-app-token` action (v3.2.0,
`bcd2ba49218906704ab6c1aa796996da409d3eb1`), reading the public client id from an
org variable and the private key from an org secret — never a PAT. The App is a
narrow, non-webhook (`active:false`), token-minting identity created through the
committed manifest flow; artifact signing is kept separate and keyless via the
run's ephemeral `GITHUB_TOKEN` + OIDC, as SLSA L3 requires.

**Action Required:** Confirm the App id (`4139655`) against the live App record;
it is not asserted by any file opened for this audit, so its row is marked
pending rather than cited.
