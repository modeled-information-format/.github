# attested-delivery documentation hub

This is the org-side entry point to the attested-delivery documentation. Following
the **DRY principle**, every fact has exactly one home and this hub only *links*:

- **Ecosystem-level docs** (attestation/SLSA concepts, the gate map, the promotion
  pipeline, the central reusable workflows, the catalog-updater) live in the
  **deployed docs site** — Astro Starlight, built from `attested-delivery/docs-site`:
  **<https://attested-delivery.github.io/docs/>**
- **Per-repo specifics** live in each project repo's own Diátaxis docs, indexed by
  that repo's `docs/README.md`.

## The ecosystem corpus (Diátaxis, on the docs site)

| Quadrant | Start here |
| --- | --- |
| Ecosystem hub (map) | <https://attested-delivery.github.io/docs/ecosystem/> |
| Tutorial | <https://attested-delivery.github.io/docs/tutorials/verify-your-first-attested-release/> |
| How-to | <https://attested-delivery.github.io/docs/guides/onboard-a-repo/> |
| Reference | <https://attested-delivery.github.io/docs/reference/quality-gate-workflows/> |
| Explanation | <https://attested-delivery.github.io/docs/concepts/> |

## In-scope project repos (their own Diátaxis docs)

| Repo | What it is | Its docs |
| --- | --- | --- |
| `rust-template` | Production Rust crate template (just recipes, SLSA L3, crates.io trusted publishing) | [docs/README.md](https://github.com/attested-delivery/rust-template/blob/main/docs/README.md) |
| `attested-iac-template` | Copier template for attested OpenTofu/Terraform (Trivy + Checkov gates) | [docs/README.md](https://github.com/attested-delivery/attested-iac-template/blob/main/docs/README.md) |
| `attested-pipeline-template` | Language-agnostic attested release pipeline template (Copier) | [docs/README.md](https://github.com/attested-delivery/attested-pipeline-template/blob/main/docs/README.md) |
| `claude-code-plugins` | Attested Claude Code plugin marketplace (catalog-admission, fail-closed) | [docs/README.md](https://github.com/attested-delivery/claude-code-plugins/blob/main/docs/README.md) |

## Operating this org

- [`onboarding/RUNBOOK.md`](./onboarding/RUNBOOK.md) — how the org was constituted and is operated.
- [`../catalog-update/README.md`](../catalog-update/README.md) — the attested plugin catalog-updater.
