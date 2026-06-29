---
title: "Artifact Signing, SLSA Attestation & Fail-Closed Verification"
description: "The org signs and attests every release artifact — SLSA build provenance, CycloneDX SBOM, vulnerability and SAST scan verdicts — keyless via Sigstore OIDC (GitHub artifact attestations and cosign), then verifies signer identity and required predicates fail-closed in-run before any publication or promotion; every attestation is independently re-verifiable with `gh attestation verify` or `cosign verify`."
type: adr
category: process
tags:
  - signing
  - cosign
  - slsa
  - attestation
  - sbom
  - verification
  - supply-chain
  - release
status: accepted
created: 2026-06-29
updated: 2026-06-29
author: MIF Maintainers
project: modeled-information-format
technologies:
  - github-actions
  - sigstore
  - cosign
  - slsa
  - sbom
  - in-toto
audience:
  - developers
  - architects
  - maintainers
related:
  - ADR-002-reusable-quality-gate-architecture.md
  - ADR-003-sast-gate-suite.md
  - ADR-004-supply-chain-scanning.md
  - ADR-007-scorecard-posture.md
---

# ADR-005: Artifact Signing, SLSA Attestation & Fail-Closed Verification

## Status

Accepted

## Context

### Background and Problem Statement

The `modeled-information-format` org publishes release artifacts that consumers
fetch and pin: source archives, container images, and the marketplace catalog
blob. A consumer who downloads one of these cannot, on its own, tell a
legitimate artifact from a tampered one, nor establish which workflow produced
it at which commit. The org's quality gates (SAST, SCA, container/IaC scanning,
posture) produce *evidence* — a clean Security tab, a SARIF file — but evidence
sitting in a tab is not a portable, enforceable claim. To gate promotion and
deployment on a gate's result, that result must become a signed object bound to
the exact artifact it describes.

Two distinct signing problems exist. First, **artifacts and their gate verdicts
need provenance and predicates** bound by digest. Second, **the signing step
must run somewhere the application repo cannot tamper with it** — otherwise the
provenance subject identity collapses to the caller and the SLSA isolation
guarantee is lost. This ADR records the decision to solve both with keyless
Sigstore signing executed inside centralized reusable workflows, to attest a
fixed set of predicate types, and to verify signer identity and required
predicates fail-closed before publication or promotion.

### Current Limitations Before This Decision

- Release artifacts (source archives, images, the catalog blob) carried no
  provenance, no SBOM, and no signature. There was no machine-verifiable
  supply-chain signal for a consumer who pinned them.
- Quality-gate results existed only as Security-tab evidence, not as
  digest-bound signed claims that a downstream deploy job could require.
- No fail-closed boundary prevented an unverified or misattributed artifact
  from being uploaded to a release or promoted between registries.
- No canonical, independently runnable verification command existed for
  consumers or for between-hop promotion checks.

## Decision Drivers

### Primary Decision Drivers

1. **No long-lived signing keys**: A stored private key is a standing theft
   target and an operational burden (rotation, storage, access). Signing must be
   keyless — short-lived Fulcio certificates bound to the run's OIDC identity,
   witnessed in Rekor.
2. **Tamper-proof signer identity (SLSA Build L3 isolation)**: The identity that
   signs must be a centralized workflow the calling repo cannot modify, so the
   provenance subject is the central `job_workflow_ref`, not the caller. A repo
   must not be able to forge provenance for its own artifacts.
3. **Fail-closed publication and promotion**: An artifact whose signature or
   required predicate does not verify in-run must never reach a release or the
   next registry hop. Upload/promotion must sit behind a passing verify step,
   and an empty required-predicate set must itself fail.
4. **Independent re-verifiability**: Every attestation must be verifiable by any
   third party with a single command and no trust in the transport layer.

### Secondary Decision Drivers

1. **One seam for every gate**: Each quality gate emits a different evidence
   format. A single reusable "seam" should turn any evidence file into a signed,
   digest-bound custom predicate, so gate logic and signing logic stay
   separated and reused, not re-implemented per gate.
2. **Cover every artifact shape**: The org ships container images (OCI
   referrers), source archives (file subjects), and a plain JSON blob (the
   catalog). The signing approach must cover all three.
3. **Correct signer scoping on verify**: Because the Fulcio SAN under L3 is the
   *signer* workflow rather than the caller, verification must pin
   `--signer-workflow` (or a certificate-identity regex), and must verify one
   signer per invocation — mixing predicates from different signers in one call
   would fail closed on a valid artifact.

## Considered Options

### Option 1: Plain unsigned artifacts (status quo)

**Description**: Continue publishing releases, images, and the catalog with no
provenance, SBOM, or signature.

**Advantages**:

- Zero workflow complexity.

**Disadvantages**:

- No consumer-verifiable provenance; a compromised artifact is
  indistinguishable from a legitimate one.
- Gate results stay un-enforceable evidence — nothing downstream can require
  them.

**Risk Assessment**:

- **Technical Risk**: High. No integrity signal for any pinned artifact.

### Option 2: Long-lived signing keys (GPG / keyed cosign)

**Description**: Hold an organization signing key in secrets and sign artifacts
with it.

**Advantages**:

- Conceptually simple; offline verification with a published public key.

**Disadvantages**:

- A standing private key is a theft target and requires rotation, storage, and
  access controls.
- The key, not the producing workflow, becomes the identity — it does not bind
  an artifact to the workflow and commit that produced it, so it does not give
  SLSA build provenance.

**Risk Assessment**:

- **Technical Risk**: Medium–High. Key compromise forges arbitrary signatures;
  no build-isolation guarantee.

### Option 3: Keyless signing without fail-closed in-run verification

**Description**: Sign and attest keyless via Sigstore, but treat verification as
an out-of-band consumer concern; publish/promote without an in-run verify step.

**Advantages**:

- No long-lived key; provenance is produced.

**Disadvantages**:

- A broken or misattributed attestation is not caught before publication. The
  artifact ships, and the defect surfaces only when (if) a consumer verifies.
- No enforcement boundary between "signed" and "shippable".

**Risk Assessment**:

- **Technical Risk**: Medium. Provenance exists but is not enforced at the gate.

### Option 4: Keyless Sigstore signing in centralized reusable workflows, attestation seam, fail-closed in-run verification, independently re-verifiable (chosen)

**Description**: Execute all signing keyless via Sigstore (the run's OIDC
id-token; Fulcio + Rekor) inside centralized reusable workflows the caller
cannot modify, so the signer identity is the central `job_workflow_ref`
(SLSA Build L3 isolation). Bind SLSA build provenance and a CycloneDX SBOM to
each artifact by digest; turn each quality-gate's evidence into a signed,
digest-bound in-toto custom predicate through a single attestation seam
(`reusable-attest-scan.yml`). Self-verify in-run before publication and re-verify
fail-closed between promotion hops, pinning the expected signer identity. Every
attestation re-verifies independently with `gh attestation verify` (GitHub
artifact attestations) or `cosign verify` / `cosign verify-blob` (cosign).

**Advantages**:

- No long-lived key; short-lived Fulcio certs only.
- SLSA L3 isolation: the application repo cannot forge its own provenance.
- One seam signs every gate verdict; gate logic and signing stay separate.
- Covers images (OCI referrers), source archives (file subjects), and the
  catalog blob.
- Fail-closed: publication/promotion sits behind verification; an empty
  required-predicate set fails.
- Re-verifiable by anyone with one command.

**Disadvantages**:

- Requires third-party actions on the org Actions allow-list
  (`sigstore/cosign-installer`, `anchore/sbom-action`, `anchore/scan-action`).
- Verification must be invoked once per signer group, because one call verifies
  a single signer identity.

**Risk Assessment**:

- **Technical Risk**: Low. Each component is independently auditable; the
  fail-closed design keeps unverified artifacts out of releases and promotions.

## Decision

The org signs and attests every release artifact keyless via Sigstore and
verifies signer identity and required predicates **fail-closed** in-run before
publication or promotion. All signing executes inside **centralized reusable
workflows** so the Fulcio SAN is the central signer workflow, not the caller
(SLSA Build L3 isolation).

**Signing primitives (two, by artifact shape):**

- **GitHub artifact attestations** (`actions/attest-build-provenance`,
  `actions/attest-sbom`, `actions/attest`) — keyless via the run's OIDC
  id-token — bind SLSA build provenance, a CycloneDX SBOM, and custom
  in-toto predicates to a subject by digest. Used for source archives and as
  the attestation seam for gate verdicts.
- **cosign keyless** (`cosign sign`, `cosign attest`, `cosign sign-blob`) — for
  container images (signature + SBOM + vuln predicate pushed as OCI referrers)
  and for the marketplace catalog **blob**, which is not a registry package.

**Image path — `sign-and-attest.yml` (the SLSA Build L3 isolation boundary).**
Application repos call it by `uses:` and cannot modify the signing steps. With
`id-token: write`, `attestations: write`, and `packages: write`, it generates
SLSA build provenance over the image digest (pushed as an OCI referrer), signs
the image keyless with cosign, generates and attests a CycloneDX SBOM, runs a
Grype vulnerability scan and attests its report as an
`https://in-toto.io/attestation/vulns/v0.1` predicate (scan does not fail the
build — attest the result; gate at promotion/admission), then self-verifies the
SLSA L3 provenance in-run with `gh attestation verify --signer-workflow … --predicate-type https://slsa.dev/provenance/v1`,
closing the loop before any promotion.

**Source-archive path — `attest-release.yml`.** On `release: published` (and via
`workflow_dispatch` to re-attest an existing tag), it packages the repo at the
tag as a reproducible `git archive` tarball, computes the tarball's `sha256`
subject digest, generates a CycloneDX SBOM, binds SLSA build provenance
(`actions/attest-build-provenance`) and the SBOM (`actions/attest-sbom`) to the
tarball, uploads artifact and SBOM to the release, and — through the seam — runs
SAST (Semgrep) and binds its SARIF to the **same** tarball digest as a signed
`https://modeled-information-format.github.io/attestations/sast/v1` predicate.
DAST is intentionally not attested here: this repo has no deployed target.

**Blob path — `reusable-cosign-sign.yml`.** Installs cosign, signs the blob
keyless with `cosign sign-blob` into a `.cosign.bundle`, then re-verifies the
bundle in-run (fail-closed) against this reusable's own signer-identity regex
before exposing it as an artifact. Anyone re-verifies with `cosign verify-blob`.

**The attestation seam — `reusable-attest-scan.yml`.** Turns any gate's evidence
file (SARIF/JSON, load-test summary, OpenVEX, …) into a signed, digest-bound
in-toto attestation via `actions/attest` with a caller-supplied
`predicate-type`. A clean Security tab is evidence; this attestation is the
enforceable, verifiable claim. Only `workflow_call` inputs and the downloaded
evidence artifact are used — no untrusted input reaches a shell.

**Verification (fail-closed, signer-pinned, re-runnable):**

- **In-run self-verify** before publish/promote: `sign-and-attest.yml` verifies
  its own SLSA provenance; `reusable-cosign-sign.yml` verifies its own blob
  bundle.
- **`verify-attestation.yml`** — fail-closed gate (e.g. between registry hops
  and before deploy): pins the expected cosign certificate identity to the
  centralized `sign-and-attest.yml`, runs `cosign verify`, `gh attestation
  verify` for SLSA provenance with `--signer-workflow`, and `cosign
  verify-attestation` for the SBOM. Rejects a signature from any other identity.
- **`reusable-verify-gates.yml`** — fail-closed verification of gate predicates:
  loops `gh attestation verify --owner --signer-workflow --predicate-type` over
  each required predicate type and exits non-zero on any failure. An empty
  predicate-type list fails closed. **One signer per invocation** — different
  predicates are signed by different workflows (the seam signs SARIF gates,
  OpenVEX self-signs in `reusable-vex.yml`), so call this once per signer group;
  mixing signers fails closed on a valid artifact.

All signer identities resolve to workflows under
`modeled-information-format/.github/.github/workflows/`; the OIDC issuer is
always `https://token.actions.githubusercontent.com`. Every `uses:` reference is
SHA-pinned to a full 40-character commit (the org enforces this via `pin-check`).

## Consequences

### Positive

1. **No standing key risk**: All signing is keyless with short-lived Fulcio
   certificates; there is no private key to rotate or steal.
2. **Forgery-resistant provenance**: SLSA L3 isolation makes the central
   reusable workflow the signer identity, so a caller repo cannot forge
   provenance for its own artifacts.
3. **Enforceable gate verdicts**: The seam turns every gate's evidence into a
   signed, digest-bound predicate a downstream job can require.
4. **Fail-closed publication and promotion**: Upload and promotion sit behind
   verify steps that pin the expected signer; an empty required-predicate set
   fails rather than passing vacuously.
5. **Independent re-verifiability**: Any consumer verifies with one command and
   no transport trust.

### Negative

1. **Allow-list additions**: `sigstore/cosign-installer`, `anchore/sbom-action`,
   and `anchore/scan-action` are third-party actions that must be on the org
   Actions allow-list before these workflows run.
2. **One signer per verify call**: Because the Fulcio SAN is the signer
   workflow, verifying predicates from multiple signers requires multiple
   `reusable-verify-gates.yml` invocations; a single mixed call fails closed on
   a valid artifact.

### Neutral

1. **GHCR auth constraint**: The image path authenticates to GHCR with the
   run's own `GITHUB_TOKEN` (a GitHub App installation token is rejected by
   GHCR's data plane), which fixes the login mechanism for the provenance
   referrer push and the cosign pushes.
2. **Registry-specific verify setup**: `verify-attestation.yml` optionally
   assumes an AWS role and logs into ECR, or logs into GHCR, depending on the
   image ref — a deliberate breadth, not added complexity for a single
   registry.
3. **SHA-pin maintenance**: Pinning every action to a full commit SHA (over a
   floating tag) is the correct posture but requires a deliberate update step
   when an action is bumped.

## Decision Outcome

Every release artifact in the org — source archive, container image, and the
marketplace catalog blob — is signed and attested keyless via Sigstore, with
SLSA build provenance, a CycloneDX SBOM, and (for images) a vulnerability
predicate, plus seam-signed gate verdicts bound by digest. Signing runs inside
centralized reusable workflows (SLSA Build L3 isolation). Publication and
promotion are fail-closed behind signer-pinned verification, and every
attestation re-verifies independently.

### Implementation

**Verify a source-archive release (consumer command):**

```bash
gh attestation verify modeled-information-format-1.0.0.tar.gz \
  --owner modeled-information-format \
  --predicate-type https://slsa.dev/provenance/v1
```

**Verify an image signature + SLSA provenance (signer pinned):**

```bash
cosign verify "ghcr.io/modeled-information-format/<app>@sha256:<digest>" \
  --certificate-identity-regexp \
  '^https://github.com/modeled-information-format/\.github/\.github/workflows/sign-and-attest\.yml@.*$' \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com"

gh attestation verify "oci://ghcr.io/modeled-information-format/<app>@sha256:<digest>" \
  --repo modeled-information-format/<app> \
  --signer-workflow modeled-information-format/.github/.github/workflows/sign-and-attest.yml \
  --predicate-type https://slsa.dev/provenance/v1
```

**Verify the catalog blob:**

```bash
cosign verify-blob .claude-plugin/marketplace.json \
  --bundle marketplace.json.cosign.bundle \
  --certificate-identity-regexp \
  '^https://github.com/modeled-information-format/\.github/\.github/workflows/reusable-cosign-sign\.yml@' \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com"
```

**Signer-workflow identities (Fulcio SAN, SLSA L3):**

- Images / SLSA provenance + SBOM: `modeled-information-format/.github/.github/workflows/sign-and-attest.yml`
- Seam-signed gate predicates (SARIF, etc.): `modeled-information-format/.github/.github/workflows/reusable-attest-scan.yml`
- Catalog blob: `modeled-information-format/.github/.github/workflows/reusable-cosign-sign.yml`

**Attested predicate types:**

- `https://slsa.dev/provenance/v1` (SLSA build provenance)
- CycloneDX SBOM (`cyclonedx` / `actions/attest-sbom`)
- `https://in-toto.io/attestation/vulns/v0.1` (Grype vulnerability report, images)
- `https://modeled-information-format.github.io/attestations/sast/v1` (seam-signed SAST verdict)

**Pinned action SHAs (signing/attest/verify):**

- `sigstore/cosign-installer@6f9f17788090df1f26f669e9d70d6ae9567deba6` (v4.1.2)
- `actions/attest-build-provenance@a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32` (v4.1.0)
- `actions/attest-sbom@c604332985a26aa8cf1bdc465b92731239ec6b9e` (v4.1.0)
- `actions/attest@59d89421af93a897026c735860bf21b6eb4f7b26` (v4.1.0)
- `anchore/sbom-action@e22c389904149dbc22b58101806040fa8d37a610` (v0.24.0)
- `anchore/scan-action@e1165082ffb1fe366ebaf02d8526e7c4989ea9d2` (v7.4.0)

**Workflow files:** `.github/workflows/sign-and-attest.yml`,
`.github/workflows/attest-release.yml`,
`.github/workflows/reusable-attest-scan.yml`,
`.github/workflows/reusable-cosign-sign.yml`,
`.github/workflows/verify-attestation.yml`,
`.github/workflows/reusable-verify-gates.yml`.

## Related Decisions

- [ADR-002: Reusable Quality-Gate Architecture](ADR-002-reusable-quality-gate-architecture.md) -- the gates whose evidence the attestation seam turns into signed, digest-bound predicates.
- [ADR-004: Supply-Chain Scanning](ADR-004-supply-chain-scanning.md) -- the SCA/SBOM/vulnerability scans whose verdicts are attested and verified fail-closed here.
- [ADR-007: Scorecard Posture](ADR-007-scorecard-posture.md) -- posture assessment; this ADR's keyless-signing and SHA-pinning posture aligns with the Scorecard checks.

## Links

- [SLSA Build provenance / GitHub artifact attestations](https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds) -- the mechanism behind `actions/attest-*`.
- [SLSA Build L3 (isolation requirement)](https://slsa.dev/spec/v1.0/levels#build-l3) -- why signing runs in a centralized workflow the caller cannot modify.
- [cosign keyless signing (Fulcio + Rekor)](https://docs.sigstore.dev/cosign/signing/overview/) -- the keyless signing model.
- [SLSA Build provenance specification](https://slsa.dev/provenance/v1) -- the provenance predicate type.
- [CycloneDX SBOM specification](https://cyclonedx.org/specification/overview/) -- the SBOM format.

## More Information

- **Date:** 2026-06-29
- **Source:** `.github/workflows/sign-and-attest.yml`, `.github/workflows/attest-release.yml`, `.github/workflows/reusable-attest-scan.yml`, `.github/workflows/reusable-cosign-sign.yml`, `.github/workflows/verify-attestation.yml`, `.github/workflows/reusable-verify-gates.yml`.
- **Related ADRs:** ADR-002, ADR-004, ADR-007

## Audit

### 2026-06-29

**Status:** Compliant

**Findings:**

| Finding | Files | Lines | Assessment |
|---------|-------|-------|------------|
| `sign-and-attest.yml` is the SLSA Build L3 isolation boundary; callers cannot modify signing steps, so provenance subject is the central `job_workflow_ref` | `.github/workflows/sign-and-attest.yml` | L1-L17 | compliant |
| Image job grants `id-token: write`, `attestations: write`, `packages: write`, `contents: read` (keyless OIDC + persist attestation + push referrers) | `.github/workflows/sign-and-attest.yml` | L57-L61 | compliant |
| SLSA build provenance over image digest pushed as OCI referrer via `actions/attest-build-provenance@a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32` (`push-to-registry: true`) | `.github/workflows/sign-and-attest.yml` | L85-L90 | compliant |
| Keyless cosign image signature; CycloneDX SBOM generated (`anchore/sbom-action@e22c389904149dbc22b58101806040fa8d37a610`) and attested (`cosign attest --type cyclonedx`) | `.github/workflows/sign-and-attest.yml` | L93-L110 | compliant |
| Grype scan (`anchore/scan-action@e1165082ffb1fe366ebaf02d8526e7c4989ea9d2`, `fail-build: false`) attested as `https://in-toto.io/attestation/vulns/v0.1` predicate | `.github/workflows/sign-and-attest.yml` | L113-L127 | compliant |
| In-run self-verify of SLSA L3 provenance via `gh attestation verify --signer-workflow … --predicate-type https://slsa.dev/provenance/v1` before promotion | `.github/workflows/sign-and-attest.yml` | L130-L141 | compliant |
| `attest-release.yml` runs on `release: published` and `workflow_dispatch` (re-attest a tag); packages a reproducible `git archive` tarball and computes its sha256 subject digest | `.github/workflows/attest-release.yml` | L19-L27, L65-L86 | compliant |
| Source tarball gets SLSA provenance (`actions/attest-build-provenance@a2bbfa…`) and CycloneDX SBOM (`actions/attest-sbom@c604332985a26aa8cf1bdc465b92731239ec6b9e`) bound by digest | `.github/workflows/attest-release.yml` | L88-L105 | compliant |
| SAST (Semgrep) SARIF bound to the SAME tarball digest as `…/attestations/sast/v1` predicate through the seam (`reusable-attest-scan.yml`) | `.github/workflows/attest-release.yml` | L125-L138 | compliant |
| Attestation seam turns any evidence file into a signed digest-bound in-toto custom predicate via `actions/attest@59d89421af93a897026c735860bf21b6eb4f7b26` | `.github/workflows/reusable-attest-scan.yml` | L78-L84 | compliant |
| Catalog blob signed keyless (`cosign sign-blob`) and re-verified in-run fail-closed against this reusable's signer-identity regex before artifact upload | `.github/workflows/reusable-cosign-sign.yml` | L70-L89 | compliant |
| `verify-attestation.yml` pins expected cosign cert identity to centralized `sign-and-attest.yml`; runs `cosign verify`, `gh attestation verify` (SLSA), `cosign verify-attestation` (SBOM) | `.github/workflows/verify-attestation.yml` | L26-L30, L85-L115 | compliant |
| `reusable-verify-gates.yml` loops `gh attestation verify --owner --signer-workflow --predicate-type` per required predicate, exits non-zero on any failure; empty predicate list fails closed; one signer per invocation | `.github/workflows/reusable-verify-gates.yml` | L11-L15, L93-L106 | compliant |

**Summary:** Signing across the org is keyless via Sigstore (the run's OIDC
id-token; Fulcio + Rekor) and executes inside centralized reusable workflows, so
the signer identity is the central workflow (SLSA Build L3 isolation). SLSA build
provenance, a CycloneDX SBOM, an image vulnerability predicate, and seam-signed
gate verdicts are bound to artifacts by digest. Publication and promotion are
fail-closed behind signer-pinned verification — in-run self-verify, plus
`verify-attestation.yml` and `reusable-verify-gates.yml`, the latter failing on
an empty required-predicate set. Every attestation re-verifies independently
with `gh attestation verify` / `cosign verify`. All `uses:` references are
SHA-pinned to full 40-character commits.

**Action Required:** None.
