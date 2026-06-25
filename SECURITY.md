# Security Policy

## Consuming Reusable Workflows

When consuming reusable workflows from this repository, pin every `uses:` to the
**full 40-char commit SHA** of the release you've reviewed and trust — never a
floating tag or branch ref. Dependabot's `github-actions` ecosystem keeps the pin
current via automated PRs.

```yaml
uses: modeled-information-format/.github/.github/workflows/<workflow>.yml@<full-sha> # vX.Y.Z
```

Check the [latest release](https://github.com/modeled-information-format/.github/releases)
for the current recommended SHA and changelog.

| Version | Supported |
|---------|-----------|
| Latest release | Yes |
| Prior releases | Best-effort |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly.

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Use [GitHub private vulnerability reporting](https://github.com/modeled-information-format/.github/security/advisories/new)
to disclose directly to maintainers. Include:

1. A description of the vulnerability
2. Steps to reproduce the issue
3. Potential impact assessment
4. Any suggested fixes (if applicable)

## Response Timeline

- **Acknowledgment**: Within 48 hours of receipt
- **Initial assessment**: Within 5 business days
- **Resolution target**: Within 30 days for confirmed vulnerabilities

## Disclosure Policy

We follow coordinated disclosure. We ask that you:

1. Allow us reasonable time to address the issue before public disclosure
2. Make a good-faith effort to avoid privacy violations, data loss, and service disruption
3. Do not exploit the vulnerability beyond what is necessary to demonstrate it

## Verifying Release Artifacts

Repositories onboarded to the attested release architecture sign container images
through the centralized signer workflow in this repository
(`modeled-information-format/.github/.github/workflows/sign-and-attest.yml`). Each release
digest carries SLSA provenance, a keyless signature, a CycloneDX SBOM, and a
vulnerability report as OCI referrers. Verify from any workstation with `gh`
(authenticated) and `cosign`:

```sh
# 0. Resolve the digest for a tag
DIGEST=$(gh api 'orgs/modeled-information-format/packages/container/<name>/versions?per_page=100' \
  --jq '[.[] | select((.metadata.container.tags // []) | index("<tag>"))][0].name')

# 1. SLSA provenance
gh attestation verify "oci://ghcr.io/modeled-information-format/<repo>@${DIGEST}" \
  --repo modeled-information-format/<repo> \
  --signer-workflow modeled-information-format/.github/.github/workflows/sign-and-attest.yml \
  --predicate-type https://slsa.dev/provenance/v1

# 2. Keyless signature
cosign verify "ghcr.io/modeled-information-format/<repo>@${DIGEST}" \
  --certificate-identity-regexp '^https://github.com/modeled-information-format/\.github/\.github/workflows/sign-and-attest\.yml@.*$' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com

# 3. SBOM attestation
cosign verify-attestation "ghcr.io/modeled-information-format/<repo>@${DIGEST}" \
  --type cyclonedx \
  --certificate-identity-regexp '^https://github.com/modeled-information-format/\.github/\.github/workflows/sign-and-attest\.yml@.*$' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com

# 4. Release binaries
gh release download <tag> --repo modeled-information-format/<repo>
gh attestation verify <binary> --repo modeled-information-format/<repo>
```

## Verifying Quality-Gate Attestations

Repositories wired to the attested quality gates additionally record a signed,
digest-bound attestation for each CI gate — SAST, SCA, container/IaC/license scan,
DAST, supply-chain posture, and vulnerability disposition.

```sh
SUBJECT=oci://ghcr.io/modeled-information-format/<repo>@${DIGEST}
SEAM=modeled-information-format/.github/.github/workflows/reusable-attest-scan.yml

# Seam-signed gate (SAST shown; swap predicate-type for other SARIF gates)
gh attestation verify "$SUBJECT" --owner modeled-information-format --signer-workflow "$SEAM" \
  --predicate-type https://mif.dev/attestations/sast/v1

# DAST (ZAP) verdict — seam-signed, same signer workflow
gh attestation verify "$SUBJECT" --owner modeled-information-format --signer-workflow "$SEAM" \
  --predicate-type https://mif.dev/attestations/dast/v1

# Vulnerability disposition (OpenVEX — self-signed by reusable-vex.yml)
gh attestation verify "$SUBJECT" --owner modeled-information-format \
  --signer-workflow modeled-information-format/.github/.github/workflows/reusable-vex.yml \
  --predicate-type https://openvex.dev/ns/v0.2.0
```
