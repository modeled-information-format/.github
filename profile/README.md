# attested-delivery

**Document, validate, share, and promulgate attested-workflow practices in GitHub.**

---

## Mission

`attested-delivery` is an open organization dedicated to making signed, SLSA-attested, fail-closed-verified release pipelines the standard — not the exception.

The work here is practical: reusable GitHub Actions workflows, reference documentation, and the canonical predicate schemas for signing and verifying quality-gate evidence. Every pattern is designed to be adopted by any repo with a few lines of YAML.

---

## What's Here

### Reusable Workflows (`.github/.github/workflows/`)

A cohesive set of `workflow_call` reusable workflows that together implement the attested release architecture:

| Workflow | Purpose |
|----------|---------|
| `pin-check` | Assert every `uses:` in a caller's workflows is pinned to a full 40-char commit SHA |
| `reusable-attest-scan` | The attestation seam — turn any scanner's evidence file into a signed, digest-bound in-toto attestation |
| `reusable-verify-gates` | Fail-closed gate verification before any publish or deploy |
| `reusable-sast-codeql` | SAST via GitHub CodeQL (SARIF → code scanning hub → attestation) |
| `reusable-sca-osv` | SCA via OSV-Scanner + dependency-review PR gate |
| `reusable-scorecard` | OpenSSF Scorecard supply-chain posture |
| `reusable-trivy` | Container image, IaC misconfiguration, and license scan |
| `reusable-vex` | OpenVEX vulnerability disposition — sign a VEX document as an attestation |
| `reusable-zap` | OWASP ZAP DAST full scan (opt-in) |
| `reusable-k6` | Grafana k6 load / performance gate with optional attestation |

### Attestation Predicate Schemas

Custom predicate type URIs are defined at `https://attested-delivery.github.io/attestations/<gate>/v1`.

### Community Health Defaults

`SECURITY.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SUPPORT.md`, issue templates, and PR template — applied org-wide by default.

---

## Core Pattern

```text
build → gate (SAST/SCA/scan/...) → attest evidence → verify all gates → deploy
```

Every gate produces evidence. Every piece of evidence is signed and bound to the artifact digest. Deployment is gated on verification — not on the gate having run, but on its attestation being present and valid.

---

## Principles

1. **Verification over trust** — consumers verify; they do not take the producer's word for it.
2. **Fail closed** — an absent or invalid attestation stops the pipeline.
3. **Ephemeral credentials only** — all signing uses the GitHub OIDC token; no long-lived secrets.
4. **SHA-pinned always** — every `uses:` is pinned to a full 40-char commit SHA. Floating tags are a supply-chain risk.

---

## Getting Started

- Read [`SECURITY.md`](https://github.com/attested-delivery/.github/blob/main/SECURITY.md) to understand how to verify release artifacts.
- Read [`CONTRIBUTING.md`](https://github.com/attested-delivery/.github/blob/main/CONTRIBUTING.md) to propose changes to the shared workflows.
- Browse `.github/workflows/` for the reusable workflow reference.

---
