# modeled-information-format — org constitution runbook

How the `modeled-information-format` org is constituted as a secure,
attested-workflow org for the **MIF (Modeled Information Format)** specification
and tooling, and how to operate it. The org reuses the attested-delivery release
architecture as its CI/release backbone; the MIF spec itself lives at
<https://mif-spec.dev>.

## Repositories

| Repo | Purpose | Notes |
| --- | --- | --- |
| `.github` | Org community-health defaults + reusable attested quality-gate workflows + signer workflows | reusables: sast-codeql, sca-osv, trivy, checkov, scorecard, vex, attest-scan, verify-gates, actionlint, sign-and-attest, verify-attestation, pin-check |
| `MIF` | The Modeled Information Format specification, JSON Schemas, and `mif_convert` tooling | flagship; migrating from `zircote/MIF` (branch `develop/v1.0.0`) |
| `attested-pipeline-template` | Language-agnostic attested release pipeline | template |
| `rust-template` | Rust attested template (5-platform build, SBOM, gates) | template |
| `attested-iac-template` | OpenTofu/Terraform attested IaC template (module + per-cloud examples, Checkov gate) | template |
| `docs-site` | Astro Starlight docs site for the release-architecture ecosystem | distinct from the MIF spec site at mif-spec.dev |

## Automation identity — GitHub App `modeled-information-format-ci`

To be created + installed org-wide (all repos). The private key lives outside any
repo (referenced by name only). The App is the org automation identity (repo
provisioning, cross-repo dispatch). It is **not** used for artifact signing or
GHCR — in-workflow signing uses the run's own ephemeral `GITHUB_TOKEN` + OIDC
`id-token`, which is what SLSA L3 requires.

Create from `repos/.github/docs/onboarding/app/manifest.json` via the manifest
flow (`docs/onboarding/app/create-app.html`); exchange the `?code=` with
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
gh release download <tag> --repo modeled-information-format/<repo> --pattern '<artifact>'
gh attestation verify <artifact> --repo modeled-information-format/<repo>
gh attestation verify <artifact> --repo modeled-information-format/<repo> --predicate-type https://cyclonedx.org/bom
```

## Status (constitution in progress)

- [ ] `.github` repo pushed (community health + reusable workflows) — rebrand complete locally, push pending
- [ ] Org hardened via `org/harden.sh` (`admin:org` token)
- [ ] 2FA + Actions allow-list/SHA-pinning applied (UI)
- [ ] GitHub App `modeled-information-format-ci` created + installed org-wide
- [ ] Template repos replicated, slug-repointed, sibling-workflow SHAs re-pinned
- [ ] Org secrets/variables mirrored
- [ ] MIF spec repo migrated from `zircote/MIF`
