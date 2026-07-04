# modeled-information-format documentation hub

This is the org-side entry point to the modeled-information-format documentation. Following
the **DRY principle**, every fact has exactly one home and this hub only *links*:

- **Ecosystem-level docs** (attestation/SLSA concepts, the gate map, the promotion
  pipeline, the central reusable workflows, the catalog-updater) live in the
  **deployed docs site** — Astro Starlight at `modeled-information-format.github.io`, served from this `.github` repo:
  **<https://modeled-information-format.github.io/docs/>**
- **Per-repo specifics** live in each project repo's own Diátaxis docs, indexed by
  that repo's `docs/README.md`.

## The ecosystem corpus (Diátaxis, on the docs site)

| Quadrant | Start here |
| --- | --- |
| Ecosystem hub (map) | <https://modeled-information-format.github.io/docs/ecosystem/> |
| Tutorial | <https://modeled-information-format.github.io/docs/tutorials/verify-your-first-attested-release/> |
| How-to | <https://modeled-information-format.github.io/docs/guides/onboard-a-repo/> |
| Reference | <https://modeled-information-format.github.io/docs/reference/quality-gate-workflows/> |
| Explanation | <https://modeled-information-format.github.io/docs/concepts/> |

## In-scope project repos (their own Diátaxis docs)

| Repo | What it is | Its docs |
| --- | --- | --- |
| `rust-template` | Production Rust crate template (just recipes, SLSA L3, crates.io trusted publishing) | [docs/README.md](https://github.com/modeled-information-format/rust-template/blob/main/docs/README.md) |
| `attested-iac-template` | Copier template for attested OpenTofu/Terraform (Trivy + Checkov gates) | [docs/README.md](https://github.com/modeled-information-format/attested-iac-template/blob/main/docs/README.md) |
| `attested-pipeline-template` | Language-agnostic attested release pipeline template (Copier) | [docs/README.md](https://github.com/modeled-information-format/attested-pipeline-template/blob/main/docs/README.md) |
| `claude-code-plugins` | Attested Claude Code plugin marketplace (catalog-admission, fail-closed) | [docs/README.md](https://github.com/modeled-information-format/claude-code-plugins/blob/main/docs/README.md) |

## Operating this org

- [`onboarding/RUNBOOK.md`](./onboarding/RUNBOOK.md) — how the org was constituted and is operated.
- [`../catalog-update/README.md`](../catalog-update/README.md) — the attested plugin catalog-updater.

### Runbooks (`docs/runbooks/`)

- [`release-runbook.md`](./runbooks/release-runbook.md) — audit-gated attested release process.
- [`branch-protection-runbook.md`](./runbooks/branch-protection-runbook.md) — consistent default-branch gates + maximum required PR checks (apply: `onboarding/org/branch-protection.sh`).
- [`labels-runbook.md`](./runbooks/labels-runbook.md) — org-centralized issue/PR labels (source: `labels.yml`, synced via `reusable-label-sync.yml`).
- [`pages-deploy-runbook.md`](./runbooks/pages-deploy-runbook.md) — how the org's Pages sites deploy, manual redeploy without a release, and the composed-site auto-publish dispatch.
