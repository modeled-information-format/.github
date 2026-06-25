---
name: attested-delivery
description: Constitute and materialize the attested release architecture — signed, SLSA-attested, fail-closed-verified releases — by wiring a repository or organization as a thin SHA-pinned caller of this org's central reusable workflows. USE THIS SKILL when user says "onboard to attested delivery", "set up release signing", "SLSA provenance", "attest releases", "wire the attestation seam", "constitute the attested architecture", "pin check", or "verify release attestations".
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# Attested Delivery — Architect & Onboarding Skill

## Purpose

Constitute and materialize the attested release architecture — signed,
SLSA-attested, fail-closed-verified releases — by wiring a repository or
organization as a **thin caller of this org's central reusable workflows**. The
reusables are bundled with this plugin under `${CLAUDE_PLUGIN_ROOT}/workflows/`
and enumerated in `references/workflow-catalog.md`; they are the same files the
org serves at `modeled-information-format/.github/.github/workflows/`. Build the wiring;
never reinvent the machinery inline.

> This skill supersedes the earlier `__ORG__`-token template flow. The current
> architecture is **central reusable workflows + the attestation seam +
> fail-closed verify-gates**, not copied per-org template files.

## Triggers

- "onboard this repo to attested delivery"
- "set up release signing / SLSA provenance"
- "wire the attested quality gates / the attestation seam"
- "constitute the attested architecture in [org]"
- "migrate CI to SHA-pinned actions with a required pin check"
- "verify release attestations"

## Composition

This skill owns the **release backbone**: SLSA Build L3 container signing
(`sign-and-attest.yml`), digest verification between hops
(`verify-attestation.yml`), the attestation seam (`reusable-attest-scan.yml`),
fail-closed deploy verification (`reusable-verify-gates.yml`), and `pin-check`.

For end-to-end **quality-gate coverage assessment** (the 12-gate map, per-gate
predicate assignment, repo-config enforcement), compose with the companion
`gh-attested` skill (installed separately — it is **not** bundled in this plugin;
if it is unavailable, do that assessment here) — do not duplicate it. Defer
build-provenance and SBOM attestation of container images to this skill's
`sign-and-attest.yml`.

## Architecture invariant

Implement a proven supply-chain architecture. The invariant: **an artifact reaches
consumers only if it is byte-identical to what was validated, carries attestations
(SLSA provenance, signature, SBOM, vuln report, gate verdicts) that re-verify at
every hop, and publication is gated on fail-closed verification.** Signing runs in
a central reusable workflow the calling repo cannot modify — so under SLSA Build L3
the Fulcio certificate identity (SAN) is the *central signer*, not the artifact
repo. Verifiers pin `--signer-workflow`.

**Before doing anything else**, read `references/platform-constraints.md`. Every
entry was paid for with a failed release; violating one produces failures whose
error messages do not name the cause.

## Operating modes — detect, then branch

Run Phase 0 first. It determines the mode:

- **Mode A — consumer repo, architecture exists.** The org already serves the
  central workflows. Wire the repo as a caller, pinned by the full 40-char commit
  SHA of `modeled-information-format/.github`. Skip Phase 1 except gap checks.
- **Mode B — constitute a new org.** An org without the architecture gets the
  central workflows on its own `.github` repo (publish this plugin's
  `${CLAUDE_PLUGIN_ROOT}/workflows/` set there, pinned), then proceeds as Mode A
  for the pilot repo. Never wire cross-org `uses:` to another org's central repo.

## Phase protocol

Each phase ends with a verify gate. Do not proceed past a failing gate.

### Phase 0 — Discovery (read-only)

1. **Default branch via API**: `gh api repos/<o>/<r> --jq .default_branch`. Never
   trust local `origin/HEAD` (constraint 8). All PRs target it.
2. **Language/build system**: lockfile + manifest detection — drives the CodeQL
   `languages` input, the SCA ecosystems, and the integration recipe.
3. **Artifact shape**: container image (single-arch / multi-arch / already pushes
   by digest) vs. static artifact (binaries, Pages site). Containers use
   `sign-and-attest.yml`; static artifacts use `actions/attest-build-provenance` +
   `anchore/sbom-action` + inline `gh attestation verify` (see
   `references/integration-recipes.md`).
4. **Registry posture**: which registries CI contacts (base images, the BuildKit
   builder image, scanner DBs); whether org policy restricts traffic.
5. **Deploy target**: none / Kubernetes / ECS / Lambda. None ⇒ Phase 5 (promotion /
   admission) is out of scope; record that explicitly.
6. **Existing CI + allow-list**: workflows, action-pinning state, branch-protection
   contexts. Confirm every third-party action a chosen gate needs is on the org
   allow-list — a missing entry startup-fails the caller with a generic "workflow
   file issue" (constraint 1). `references/workflow-catalog.md` lists the allow-list
   need per workflow.

Gate: a written discovery summary naming mode, artifact shape, in-scope workflows.

### Phase 1 — Constitute (org level; Mode B, or Mode A gap-fill)

1. The central workflows are present on the org's `.github` default branch; record
   the full HEAD SHA — it is the pin for every caller.
2. Set the central repo's Actions access level to `organization`, else every
   cross-repo `uses:` startup-fails with zero jobs (constraint 1):
   `gh api -X PUT repos/<o>/.github/actions/permissions/access -f access_level=organization`.
3. Add every required third-party action to the org allow-list **before** any
   caller references it (owner action; emit the exact list, do not apply it).

Gate: a scratch caller resolves a central reusable without startup failure.

### Phase 2 — Materialize (repo level)

Wire the repo as a thin caller. Required elements, all shapes:

1. **`pin-check` as a CI job** calling `pin-check.yml`, later a required status
   check (context `pin-check / pin-check`, constraint 12). Migrate every `uses:` to
   a full 40-char SHA with a trailing `# vX.Y.Z` comment.
2. **The in-scope gates** wired per `references/integration-recipes.md`: each SARIF
   gate uploads its evidence artifact, then the caller calls
   `reusable-attest-scan.yml` with the gate's `predicate-type` to turn the verdict
   into a signed, digest-bound attestation (the seam).
3. **Signing**: for a container, call `sign-and-attest.yml` with `image-name` +
   `image-digest` after the build pushes by digest; for a static artifact, use the
   `attest-build-provenance` + `attest-sbom` recipe.
4. **Fail-closed verify before publication/deploy**: `reusable-verify-gates.yml`
   (one `signer-workflow` per call) in the publish/deploy job's `needs:`, plus
   `verify-attestation.yml` for container provenance between hops. A tag publishes
   nothing whose required attestations do not verify.
5. **SECURITY.md** "Verifying Release Artifacts" + "Verifying Quality-Gate
   Attestations" — the exact commands from `references/verification.md`.
6. **Release dry-run**: `workflow_dispatch` + tag-gated publish jobs
   (`if: startsWith(github.ref, 'refs/tags/')`) so build → sign → verify is
   exercisable without cutting a version. Do not skip it (hard-won).
7. **`.github/dependabot.yml`** (github-actions ecosystem) to keep SHA pins fresh;
   CHANGELOG entry per repo convention.

Gate: `actionlint` clean; PR opens; pipeline green including `pin-check / pin-check`.

### Phase 3 — Protection & branch model

1. Required status checks: the in-scope gates + `pin-check / pin-check` (context name
   = `<caller job id> / <called job name>`, constraint 12).
2. Required reviews + CODEOWNERS, dismiss-stale, signed commits, linear history,
   blocked force-push. Guide owner-gated settings; never apply silently.

### Phase 4 — Verify end-to-end

1. Dispatch the dry-run (or cut the first tag). The chain must show: build →
   (gates → seam-attest) → sign-and-attest (provenance + signature + SBOM + vuln
   report) → verify (fail-closed) → publish (tag runs only).
2. Run every command in `references/verification.md` **independently** against the
   published digest — in-pipeline green is not the acceptance test.

### Phase 5 — Conditional extensions (only when Phase 0 found a deploy target)

- Promotion between environments: referrer-carrying `cosign copy` by digest +
  post-copy `verify-attestation.yml`, behind a change-record gate (an approved
  record whose digest equals the promoting digest). Promotion re-verifies, never
  rebuilds.
- Admission enforcement: Kyverno/Gatekeeper for k8s; pre-deploy
  `reusable-verify-gates.yml` for ECS/Lambda.

## Hard rules (evidence in references/platform-constraints.md)

1. **Pin every `uses:` to a full 40-char SHA** with a trailing `# vX.Y.Z`. Tags are
   mutable supply-chain risk (the March 2026 `trivy-action` compromise,
   CVE-2026-33634, force-pushed 76 of 77 tags to malware).
2. `gh attestation verify` under SLSA L3: `--owner`/`--repo` alone FAILS (the SAN is
   the central signer) — always add `--signer-workflow`, **one signer per command**.
   `--cert-identity-regexp` / `--cert-oidc-issuer` are cosign flags; `gh` rejects them.
3. Central repo Actions access level must be `organization`.
4. Default branch from the API, never local `origin/HEAD`.
5. **Signed ≠ passed** — an attestation proves a gate ran and recorded a verdict; the
   verifying policy reads the verdict field.
6. Least privilege: `id-token: write` + `attestations: write` only on signing jobs;
   `security-events: write` only on SARIF-upload jobs.
7. **Never read, write, commit, or log a secret value** — emit the name and the
   `gh secret set NAME` command only.

## References

- `references/workflow-catalog.md` — the deliberate, named index of all 19 bundled
  reusable workflows: `workflow_call` contracts, predicates, allow-list needs.
- `references/architecture.md` — the invariant, the catalog roles, caller permission
  sets, the seam, the pipeline shape.
- `references/integration-recipes.md` — per-language and per-artifact-shape caller
  recipes (container, multi-arch, static binaries) and the SHA-pin migration.
- `references/verification.md` — the complete independent verification command set,
  including seam-signed gate and OpenVEX attestations.
- `references/platform-constraints.md` — symptom → cause → fix for every trap.
- `references/rollout-checklist.md` — the phased rollout and acceptance tests.
