# attested-delivery — org constitution runbook

How the `attested-delivery` org was constituted as a secure, attested-workflow
reference org, and how to operate it. All content is sanitized of non-org names.

## Repositories

| Repo | Purpose | Notes |
| --- | --- | --- |
| `.github` | Org community-health defaults + reusable attested quality-gate workflows + signer workflows | template; reusables: sast-codeql, sca-osv, trivy, checkov, scorecard, vex, k6, zap, attest-scan, verify-gates, actionlint, sign-and-attest, verify-attestation, pin-check |
| `attested-pipeline-template` | Language-agnostic attested release pipeline | template; release `v0.1.0` published + attested |
| `rust-template` | Rust attested template (5-platform build, SBOM, gates) | template; release `v0.1.0` published + attested |
| `attested-iac-template` | OpenTofu/Terraform attested IaC template (module + per-cloud examples, Checkov gate) | template (public) |
| `docs` | Astro Starlight docs site | live at https://attested-delivery.github.io/docs/ |

## Automation identity — GitHub App `attested-delivery-ci`

Created + installed org-wide (all repos). The private key lives outside any repo
(referenced by name only). The App is the org automation identity (repo
provisioning, cross-repo dispatch). It is **not** used for artifact signing or
GHCR — in-workflow signing uses the run's own ephemeral `GITHUB_TOKEN` + OIDC
`id-token`, which is what SLSA L3 requires.

Re-create from `app/manifest.json` via the manifest flow (`app/create-app.html`)
if ever needed; exchange the `?code=` with
`gh api -X POST /app-manifests/<code>/conversions`.

## Org security (hardened)

- 2FA enforcement **required** (UI-only setting — `two_factor_requirement_enabled`
  is read-only via REST).
- `default_repository_permission: read`; members cannot create public/private
  repos or delete repos; web commit sign-off required.
- Actions policy: "Allow select actions and reusable workflows" with **require
  SHA-pinning ON** (foundational). The third-party allow-list is documented in
  `.github/README.md`. Per-repo `pin-check` jobs re-enforce SHA-pinning.

`org/harden.sh` applies the API-settable subset (requires `admin:org`); the 2FA
toggle and the Actions allow-list are UI-only.

## Verifying a release

```
gh release download <tag> --repo attested-delivery/<repo> --pattern '<artifact>'
gh attestation verify <artifact> --repo attested-delivery/<repo>
gh attestation verify <artifact> --repo attested-delivery/<repo> --predicate-type https://cyclonedx.org/bom
```

Both `attested-pipeline-template` and `rust-template` `v0.1.0` releases verify
(SLSA provenance + CycloneDX SBOM) independently from a workstation.

## Status

All five constitution objectives are complete: App identity installed, org
hardened, three templates published with `isTemplate: true`, attested release
pipelines producing independently-verifiable releases, and the docs site live.
