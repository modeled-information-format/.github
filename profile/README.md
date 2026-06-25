# Modeled Information Format (MIF)

**The opinionated, OKF-compliant content model that fills OKF's deliberately empty envelope.**

---

## Mission

[OKF](https://github.com/google/open-knowledge-format) defines the *transport
surface* — a directory of markdown files with YAML frontmatter and one required
`type` field — and deliberately leaves the **content model** open. `MIF` supplies
the concrete type system, typed relationships, provenance/trust, and
validity/freshness semantics that OKF leaves unspecified.

Every MIF bundle validates as a conformant OKF bundle — compliance as a
**superset, not by subordination**. MIF remains an independent specification with
its own identity model and governance.

**AI memory is the first domain profile of MIF, not its identity.** The same
content model carries any structured, evolving knowledge corpus.

Spec, schemas, and reference docs live at **<https://mif.dev>**.

---

## What MIF supplies (OKF's open questions, answered)

| OKF open design space | MIF's opinionated answer |
| --- | --- |
| No concept-type taxonomy | `semantic` / `episodic` / `procedural` base types |
| Untyped markdown-link edges | Typed relationships (overlay on OKF links) |
| No merge / contradiction semantics | `Supersedes`, `ConflictsWith` |
| No trust tiers | Provenance `source_type` + `trust_level` |
| Stale-vs-live left to process | Validity windows + TTL/freshness |
| No provenance | W3C PROV |
| Markdown only | First-class, derived JSON-LD projection |

- **Markdown** (`.md`) is canonical, human-readable, Obsidian-compatible.
- **JSON-LD** is a derived, regenerable projection — never hand-edited.
- Stable UUID identity survives concept relocation; JSON Schema validates the
  projection.

---

## How releases here are delivered

The MIF org ships its specifications, schemas, and tooling through a
**signed, SLSA-attested, fail-closed-verified** release backbone — centralized
reusable signing/verification workflows live in this `.github` repo and are
consumed by every project repo.

```text
build → gate (SAST/SCA/scan/...) → attest evidence → verify all gates → publish
```

Every gate produces evidence; every piece of evidence is signed and bound to the
artifact digest; publication is gated on verification, not on the gate merely
having run. Consumers verify independently with `gh attestation verify`.

### Principles

1. **Verification over trust** — consumers verify; they do not take the producer's word for it.
2. **Fail closed** — an absent or invalid attestation stops the pipeline.
3. **Ephemeral credentials only** — all signing uses the GitHub OIDC token; no long-lived secrets.
4. **SHA-pinned always** — every `uses:` is pinned to a full 40-char commit SHA.

---

## Getting Started

- Read the specification at **<https://mif.dev>**.
- Read [`SECURITY.md`](https://github.com/modeled-information-format/.github/blob/main/SECURITY.md) to verify release artifacts.
- Read [`CONTRIBUTING.md`](https://github.com/modeled-information-format/.github/blob/main/CONTRIBUTING.md) to propose changes.
- Browse `.github/workflows/` for the reusable quality-gate and signing workflows.

---
