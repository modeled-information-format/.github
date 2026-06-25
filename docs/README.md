# modeled-information-format documentation hub

This is the org-side entry point to the modeled-information-format documentation. Following
the **DRY principle**, every fact has exactly one home and this hub only *links*:

- **Ecosystem-level docs** (attestation/SLSA concepts, the gate map, the promotion
  pipeline, the central reusable workflows, the catalog-updater) live in the
  **deployed docs site** — Astro Starlight at `mif.dev`, served from this `.github` repo:
  **<https://mif.dev/docs/>**
- **Per-repo specifics** live in each project repo's own Diátaxis docs, indexed by
  that repo's `docs/README.md`.

## The ecosystem corpus (Diátaxis, on the docs site)

| Quadrant | Start here |
| --- | --- |
| Ecosystem hub (map) | <https://mif.dev/docs/ecosystem/> |
| Tutorial | <https://mif.dev/docs/tutorials/verify-your-first-attested-release/> |
| How-to | <https://mif.dev/docs/guides/onboard-a-repo/> |
| Reference | <https://mif.dev/docs/reference/quality-gate-workflows/> |
| Explanation | <https://mif.dev/docs/concepts/> |

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
