---
id: org-adr-index
type: semantic
created: 2026-06-29T00:00:00Z
diataxis_type: reference
---

# Org Architecture Decision Records

This directory holds **organization-level** Architecture Decision Records (ADRs)
for the `modeled-information-format` org — the cross-repo CI, security, release,
and governance decisions that the org's reusable workflows and shared
infrastructure implement. Repo-specific ADRs live in their own repos (for
example, `MIF/adr/`); this directory records decisions that apply org-wide.

## Format

ADRs follow the **Structured MADR** format — an extension of
[MADR](https://adr.github.io/madr/) (Markdown Architectural Decision Records)
that adds YAML frontmatter, full risk-assessed option analysis, split
Positive/Negative/Neutral consequences, and a required code-grounded **Audit**
section that cites `file:line` anchors in the workflows and scripts the decision
governs.

## Index

| ADR | Title | Status | Description |
|-----|-------|--------|-------------|
| [ADR-001](ADR-001-org-label-sync.md) | Org-Centralized Label Synchronization | Accepted | Labels are defined once in the `.github` repo's `labels.yml` and applied authoritatively to every repo by a reusable workflow through a thin SHA-pinned caller, with an optional repo-local overlay; the merge step emits JSON so colors stay strings. |
| [ADR-002](ADR-002-reusable-quality-gate-architecture.md) | Reusable Attested Quality-Gate Architecture | Accepted | All CI quality gates live as reusable workflows in `.github`, consumed by every repo as thin SHA-pinned callers under a fail-closed Actions posture (`pin-check` + `actionlint`). The umbrella the gate ADRs plug into. |
| [ADR-003](ADR-003-sast-gate-suite.md) | SAST Gate Suite (CodeQL + Semgrep + ShellCheck) | Accepted | The static-analysis layer: three reusable SAST gates — CodeQL, Semgrep, and ShellCheck — wired through caller workflows such as `sast.yml`. |
| [ADR-004](ADR-004-supply-chain-scanning.md) | Supply-Chain Scanning (OSV, Secrets, Trivy, Checkov, VEX) | Accepted | The supply-chain layer: reusable gates for dependency vulnerabilities (OSV), secret scanning, IaC/container/license scanning (Trivy, Checkov), and VEX exploitability statements. |
| [ADR-005](ADR-005-signing-attestation-verification.md) | Artifact Signing, SLSA Attestation & Fail-Closed Verification | Accepted | Release artifacts are signed and attested (cosign keyless via Sigstore, SLSA provenance, SBOM, scan verdicts) and verified fail-closed in-run before publication, with independent re-verification. |
| [ADR-006](ADR-006-dast-and-load-testing.md) | DAST and Load Testing (ZAP + k6), Opt-In Schedule/Dispatch-Driven | Accepted | Dynamic analysis (OWASP ZAP) and load testing (k6) run as opt-in, schedule/dispatch-driven reusable workflows — not PR gates — because they need a live target; findings surface as reports. |
| [ADR-007](ADR-007-scorecard-posture.md) | OpenSSF Scorecard Posture Assessment | Accepted | The org runs OpenSSF Scorecard as a reusable workflow for repository security-posture assessment, with results published. |
| [ADR-008](ADR-008-github-app-ci-identity.md) | GitHub App CI Identity (Token-Minting App vs PAT) | Superseded by [ADR-011](ADR-011-least-privilege-app-fleet.md) | Org workflows authenticate as the dedicated `modeled-information-format-ci` GitHub App via short-lived minted tokens, rather than a PAT; artifact signing instead uses the run's ephemeral `GITHUB_TOKEN` + OIDC. |
| [ADR-009](ADR-009-branch-protection-standardization.md) | Branch-Protection Standardization | Accepted | Every repo's default branch gets one identical protection posture via an idempotent declarative script — required status checks, reviews, and related rules — codified as a runbook. |
| [ADR-010](ADR-010-plugin-catalog-hub.md) | Plugin Catalog Hub and Manifest Review | Accepted | The org governs Claude Code plugin marketplaces with a verify-first catalog-update hub, a soft-fail manifest-review gate (SHA pins, reserved names, required fields → SARIF), and a hard-fail catalog-sync check, scoped by a deny-list. |
| [ADR-011](ADR-011-least-privilege-app-fleet.md) | Least-Privilege App Fleet and Org-Wide Standard Gate Suite | Accepted | Supersedes ADR-008: the single CI identity becomes five least-privilege Apps (ci, catalog, pages, automerge, release) installed org-wide, minted via the OAuth client-id under one `<ROLE>_CLIENT_APP_*` scheme in a jq-gated `auth/apps.json`; every repo standardizes on the full reusable gate suite on these shared identities. |
| [ADR-012](ADR-012-osv-scanner-rollout-completion.md) | OSV-Scanner Rollout Completion Across Org Repos | Accepted | Closes an adoption gap in ADR-004's standard SCA gate by wiring `reusable-sca-osv.yml` into doc-site, mif-docs-plugin, and research-harness-template via one reviewed PR per repo; mnemonic-vscode and design-system remain tracked exceptions. |
| [ADR-013](ADR-013-marketplace-release-automation.md) | Automated Attested Marketplace Release on Catalog Admission | Accepted | Extends ADR-010's pipeline past the admission-verified merge: a reusable auto-tag workflow, called by each marketplace on catalog-path pushes to `main`, computes the next patch version and pushes the tag with a release-App token, firing the marketplace's existing tag-gated attested release unchanged. |

## Creating new ADRs

1. Copy the structure from a recent ADR (for example [ADR-005](ADR-005-signing-attestation-verification.md)) as the Structured MADR exemplar.
2. Use sequential numbering: `ADR-NNN-short-title.md`.
3. Fill in all sections: frontmatter, Status, Context, Decision Drivers, Considered Options (with risk assessments), Decision, Consequences (Positive/Negative/Neutral), Decision Outcome, Related Decisions, Links, More Information, and Audit.
4. In the **Audit** section, cite only `file:line` anchors you have opened and confirmed; if a finding cannot be confirmed, set the audit row's assessment to `pending` rather than inventing a citation.
5. Update this index and link related ADRs bidirectionally via the `related` frontmatter.

## See also

- [Org runbooks](../runbooks/) — operational procedures (labels, branch protection, releases) that these decisions are executed through.
- [`MIF/adr/`](https://github.com/modeled-information-format/MIF/tree/main/adr) — the MIF spec's repo-level ADRs.
