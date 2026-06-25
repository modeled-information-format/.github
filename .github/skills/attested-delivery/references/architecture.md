# Architecture — invariant, components, interfaces

## The invariant

An artifact (canonically: a container digest, or a signed static artifact) may
advance — to a registry tag consumers pull, to the next environment, to
production — only when all three hold:

1. **Byte-identical** to what was validated: promotion copies by digest, never
   rebuilds, never re-tags loosely. A rebuild is a new artifact and orphans every
   attestation made about the old one.
2. **Attestations travel and re-verify**: SLSA provenance, keyless signature,
   CycloneDX SBOM, a vulnerability report, and each gate's verdict are bound to the
   digest (as OCI referrers for images, as `gh` attestations for files) and
   re-verify at each hop.
3. **Publication/promotion is fail-closed**: a verification job gates the release;
   production promotion additionally requires an approved change record whose
   recorded digest equals the digest being promoted.

## Why a reusable workflow is the signer (SLSA Build L3)

Signing runs in a centralized **reusable workflow** the calling repo cannot modify.
The Fulcio certificate's SAN (`job_workflow_ref`) is therefore the central workflow
— `modeled-information-format/.github/.github/workflows/sign-and-attest.yml@<sha>` (or
`reusable-attest-scan.yml` for gate verdicts) — while the certificate extensions
record the *caller* as the source repository and ref. Verifiers assert both
independently (source repo via `--repo` / extension 1.3.6.1.4.1.57264.1.12; signer
via `--signer-workflow` / SAN). A composite action cannot provide this isolation: it
runs in the caller's job with the caller's token.

## Components — the central catalog

The org serves 19 reusable workflows; the plugin bundles them under
`${CLAUDE_PLUGIN_ROOT}/workflows/`. `references/workflow-catalog.md` is the
authoritative per-workflow contract (inputs, secrets, outputs, permissions,
predicate, allow-list). Roles in brief:

**The signing / verification spine**

| Workflow | Role |
| --- | --- |
| `pin-check.yml` | Fail on the first `uses:` not pinned to a 40-char SHA (required check) |
| `reusable-actionlint.yml` | Workflow lint with a verified, checksum-pinned actionlint fetch |
| `reusable-attest-scan.yml` | **The seam** — sign any evidence file into a digest-bound in-toto attestation (the signer for every SARIF gate) |
| `reusable-verify-gates.yml` | Fail-closed `gh attestation verify` of gate attestations (one signer per call); put in a deploy job's `needs:` |
| `sign-and-attest.yml` | Sign + attest a **container image** by digest — SLSA Build L3 provenance, keyless cosign signature, CycloneDX SBOM, Grype vuln report, self-verify |
| `verify-attestation.yml` | Verify a digest's signature + attestations between registry hops (pins the signer to `sign-and-attest.yml`) |
| `reusable-cosign-sign.yml` | Keyless **blob** signing (e.g. a `marketplace.json` catalog) + in-run verify; consumers re-verify with `cosign verify-blob` |

**The quality gates** (each emits SARIF + an evidence artifact for the seam)

| Workflow | Gate |
| --- | --- |
| `reusable-sast-codeql.yml` | SAST (CodeQL) |
| `reusable-sca-osv.yml` | SCA (OSV-Scanner + dependency review) |
| `reusable-trivy.yml` | Container + IaC misconfig + license scan |
| `reusable-checkov.yml` | IaC policy (graph-based; no allow-list entry needed) |
| `reusable-scorecard.yml` | OpenSSF Scorecard posture (repo-level signal) |
| `reusable-vex.yml` | OpenVEX disposition (self-signs `openvex.dev/ns/v0.2.0`) |
| `reusable-k6.yml` | Load/perf (opt-in; self-signs when `attest: true`) |
| `reusable-zap.yml` | DAST (opt-in; needs a running target) |
| `reusable-secrets.yml` | Secret scanning — Gitleaks (soft-fail) + TruffleHog (verified-only, hard-fail) |
| `reusable-semgrep.yml` | SAST (source) — Semgrep, complements CodeQL |
| `reusable-shellcheck.yml` | SAST (shell hooks) — Differential ShellCheck (needs `redhat-plumbers-in-action/differential-shellcheck@*` allow-list) |
| `reusable-manifest-review.yml` | Marketplace/plugin manifest integrity (external sources SHA-pinned, required fields) |

Caller permission sets (job-level, for the `uses:` jobs):

- seam-attest (`reusable-attest-scan.yml`): `id-token: write`, `attestations: write`,
  `contents: read`
- container sign (`sign-and-attest.yml`): `id-token: write`, `attestations: write`,
  `packages: write`, `contents: read`
- container verify (`verify-attestation.yml`): `id-token: write`, `contents: read`,
  `packages: read`, `attestations: read`
- gate verify (`reusable-verify-gates.yml`): `contents: read`, `attestations: read`,
  `packages: read`
- SARIF gates: `security-events: write` + `contents: read` (+ `actions: read`, and
  `packages: read` for image scans); `reusable-sca-osv.yml`'s `dependency-review`
  job also needs `pull-requests: write`
- pin-check: `contents: read`

Conventions: every `uses:` of a central workflow is pinned `@<full 40-char SHA>`
with a trailing `# vX.Y.Z`; Dependabot's `github-actions` ecosystem keeps pins
current; inputs taking a full image reference (`image-ref`) are digest-pinned,
inputs taking a repository (`image-name`) carry no tag/digest.

## The seam — turning a verdict into an attestation

A clean SARIF in the code-scanning tab is *evidence*; the enforceable claim is the
attestation. The pattern: a gate uploads its evidence artifact (exposing
`sarif-artifact` / `sarif-filename` outputs), then the caller invokes
`reusable-attest-scan.yml` with `subject-name` + `subject-digest` and the gate's
`predicate-type` (namespace
`https://modeled-information-format.github.io/attestations/<gate>/v1`). The result is a
signed, digest-bound in-toto statement. `reusable-verify-gates.yml` re-verifies a
set of predicate types for one signer at deploy time, fail-closed.

## Registry posture (when org policy is single-registry)

Application repos pull and push **only** the org registry. Logins precede Buildx
setup so every pull (builder image, base images) is authenticated (constraint 6).
For registry-restricted orgs, pin the BuildKit builder image to a mirror via
`driver-opts: image=…`.

## Release pipeline shape (the proven caller DAG)

```text
test ─┬─ build (binary) ──────────────┬─ publish   (tag only,
      ├─ sbom / changelog / bundle ────┘             needs verify)
      ├─ gates → seam-attest ──────────┐
      └─ container-build (matrix) → container-merge (digest out)
                                  → sign-and-attest → verify ─┘
```

Publication requires `verify`. `workflow_dispatch` runs the same chain with publish
jobs tag-gated — the dry run that lets the attested chain be exercised without
cutting a version.

## CI shape (the recommended fail-fast consolidation)

Stage 0: lint (+ `pin-check` in parallel, gating merge not stages) → Stage 1: test,
the SARIF gates → Stage 2: coverage, container/image scan, seam-attest. One
concurrency group per ref; PR pushes cancel the superseded pipeline.
