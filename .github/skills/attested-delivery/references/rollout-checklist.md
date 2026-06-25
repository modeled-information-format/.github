# Rollout Checklist — phases, exit gates, acceptance tests

Pace: pilot-first, with soak windows between phases. Do not advance past a failing
exit gate. Phases 2–3 apply only when targets deploy (Phase 0 discovery decides).

The plugin's catalog (the 19 reusables) covers gates, signing, and verification.
**Promotion, DORA emission, and admission are caller-implemented extensions** built
on `verify-attestation.yml` / `reusable-verify-gates.yml` — there is no bundled
`promote`/`dora` workflow. Build them as the deploy target requires.

## Phase 0 — Constitute and prove the loop on a pilot

- [ ] Central repo (`<org>/.github`) holds the canonical reusables; every action
      inside them pinned by full SHA; Actions access level = `organization`.
- [ ] Every third-party action a chosen gate needs is on the org allow-list
      (see `references/workflow-catalog.md`); single-registry orgs authenticate
      base/builder pulls (logins before Buildx; optional mirror).
- [ ] Pilot repo wired per its shape (recipes A–D), publication gated on the
      fail-closed verify job; release dry-run dispatchable.
- [ ] pin-check job in pilot CI; full SHA migration done; required check.
- [ ] SECURITY.md verification section published in the pilot.
- [ ] **Exit gate:** AT-05 and AT-06 pass from a workstation against a published
      digest; the dry-run chain (build → gates → seam-attest → sign → verify) is green.

## Phase 1 — Standardize

- [ ] SBOM standardized (CycloneDX primary) as an attested referrer; each in-scope
      gate verdict bound to the digest via the seam.
- [ ] Pin-by-SHA codified as org policy; pin-check required on the candidate repo set.
- [ ] CODEOWNERS on the central signing/seam workflows (platform/security review
      required to change a signer).
- [ ] **Exit gate:** AT-06 (SBOM retrievable + verifiable) on all pilots; second
      repo onboarded by following the skill alone.

## Phase 2 — Promotion and governance (deploying targets only)

- [ ] Promotion between environments: referrer-carrying `cosign copy` by digest, then
      `verify-attestation.yml` at the destination (post-copy re-verify, AT-02).
- [ ] Change-record gate: promotion to production requires an approved record whose
      digest equals the promoting digest (issue↔digest equality, AT-07).
      Caller-implemented — gate the promote job on the approval.
- [ ] Deployment events emitted (deployment = prod digest promotion, AT-08);
      emit on failure too (`if: always()`). Caller-implemented.
- [ ] **Exit gate:** AT-01/AT-02/AT-07 pass; a promotion without an approved change
      record is blocked before any copy.

## Phase 3 — Admission and operations (deploying targets only)

- [ ] Admission control audit → enforce (Kyverno/Gatekeeper for k8s; pre-deploy
      `reusable-verify-gates.yml` for ECS/Lambda) (AT-01 at runtime).
- [ ] Running-digest equality checks (AT-03); rollback drill to a verified digest
      (AT-04).
- [ ] Org ruleset expansion to the full repo set.

## Acceptance tests

| ID | Property | How to check |
| --- | --- | --- |
| AT-01 | Unsigned digest denied | admission denies the pod / pre-deploy gate fails before service update |
| AT-02 | Attestations survive promotion | `cosign verify-attestation --type cyclonedx <dest>@<digest>` exits 0 at the destination registry |
| AT-03 | Running digest == approved digest | three-way sha256 equality: running workload, validated, change record |
| AT-04 | Rollback re-points to a verified digest | roll back, then run the verify set against the target digest |
| AT-05 | SLSA provenance verifies, signer pinned | `gh attestation verify oci://<image>@<digest> --repo <org>/<repo> --signer-workflow <org>/.github/.github/workflows/sign-and-attest.yml --predicate-type https://slsa.dev/provenance/v1` |
| AT-06 | Signature + SBOM verify against the central signer identity | `cosign verify` + `cosign verify-attestation --type cyclonedx` with the signer identity regexp (see verification.md) |
| AT-07 | Promotion without change record blocked | the promote job fails at the change-record gate; no copy executes |
| AT-08 | Deployment events emit | production promotion increments the deployment metric (and failures emit via `if: always()`) |
