# Workflow catalog — the 19 central reusable workflows

This is the deliberate, named index of every reusable workflow the
attested-delivery plugin ships. Each is a **bundled plugin resource**: it lives
under the plugin root and is reachable at
`${CLAUDE_PLUGIN_ROOT}/workflows/<name>.yml`. The same file is the org's
authoritative reusable workflow — there are no copies; this catalog points at the
real thing.

Each entry records the file's `on.workflow_call` contract (inputs, secrets,
outputs), the caller permissions it requires, the attestation predicate it
produces or verifies, and any third-party action that must be on the org
allow-list before a caller can resolve it. Contracts are quoted from the files;
when a default changes in the workflow, update the entry here.

**Calling convention.** Reference every workflow by the `.github` repo's full
40-char commit SHA, with the version as a trailing comment:

```yaml
uses: attested-delivery/.github/.github/workflows/<name>.yml@<sha> # vX.Y.Z
```

Resolve the SHA at use time (`gh api repos/attested-delivery/.github/git/ref/tags/<tag>`);
never trust a remembered value. `pin-check` enforces this on every caller.

---

## The signing / verification spine

### `${CLAUDE_PLUGIN_ROOT}/workflows/pin-check.yml`
Assert every `uses:` in the caller is pinned to a full 40-char commit SHA. The
required status check that makes SHA-pinning enforceable per-repo.

- **Inputs:** `scan-dir` (string, optional, default `.github`) — directory to scan.
- **Secrets:** none. **Outputs:** none.
- **Permissions:** top-level `{}`; job `pin-check` needs `contents: read`.
- **Job / check context:** job id `pin-check`, name `pin-check` → required-check
  context `pin-check / pin-check`.
- **Predicate:** none (validation gate).
- **Allow-list:** none beyond GitHub-created `actions/checkout`.

### `${CLAUDE_PLUGIN_ROOT}/workflows/reusable-actionlint.yml`
Workflow-syntax lint with a verified, pinned actionlint download (there is no
allow-listed pinned action for actionlint, so the fetch is centralized and
checksum-verified).

- **Inputs:** `version` (string, default `1.7.7`); `sha256` (string, default
  `023070a287cd8cccd71515fedc843f1985bf96c436b7effaecce67290e7e0757` — must match
  `version`); `files` (string, default `''` → all under `.github/workflows`).
- **Secrets:** none. **Outputs:** none.
- **Permissions:** `contents: read`.
- **Job:** `actionlint` / name `actionlint`.
- **Predicate:** none (lint gate).
- **Allow-list:** none beyond `actions/checkout`.

### `${CLAUDE_PLUGIN_ROOT}/workflows/reusable-attest-scan.yml` — the attestation seam
Turn any gate's evidence file into a signed, digest-bound in-toto attestation via
GitHub keyless signing (`actions/attest`, custom predicate). This is the signer
identity for every SARIF gate; verifiers pin `--signer-workflow` to this file.

- **Inputs (all required):** `subject-name` (logical subject — image repo, package,
  or artifact label); `subject-digest` (`sha256:...` the predicate binds to);
  `predicate-type` (URI, e.g. `https://attested-delivery.github.io/attestations/sast/v1`);
  `predicate-artifact` (uploaded artifact name holding the evidence);
  `predicate-filename` (evidence filename within the artifact, e.g. `results.sarif`).
- **Secrets:** none. **Outputs:** none.
- **Permissions:** job `attest` needs `id-token: write`, `attestations: write`,
  `contents: read`.
- **Job:** `attest` / name `attest`.
- **Predicate:** caller-specified custom predicate types. Self-signs via `actions/attest`.
- **Allow-list:** GitHub-created `actions/download-artifact`, `actions/attest` only.

### `${CLAUDE_PLUGIN_ROOT}/workflows/reusable-verify-gates.yml` — fail-closed verify
Run `gh attestation verify` against gate attestations and halt an unverified or
improperly-signed artifact before it ships. Put it in a deploy job's `needs:`.
**One signer per invocation** — call it once per distinct signer workflow.

- **Inputs (all required):** `subject-ref` (`oci://...@sha256` or a file path);
  `owner` (org that produced the attestations); `signer-workflow` (the single
  signer for ALL predicate-types in this call — `reusable-attest-scan.yml` for
  seam-signed gates, `reusable-vex.yml` for OpenVEX, etc.); `predicate-types`
  (newline/whitespace-separated predicate URIs, at least one).
- **Secrets:** none. **Outputs:** none.
- **Permissions:** job `verify` needs `contents: read`, `attestations: read`,
  `packages: read`.
- **Job:** `verify` / name `verify`.
- **Predicate:** none (consumes attestations; produces none).
- **Allow-list:** none (inline `gh` CLI).

### `${CLAUDE_PLUGIN_ROOT}/workflows/sign-and-attest.yml` — container SLSA Build L3
Sign and attest a built **container image by digest**: SLSA provenance, keyless
cosign signature, CycloneDX SBOM, and a Grype vulnerability report, then
self-verifies. Image-only; not for static artifacts.

- **Inputs:** `image-name` (required — repo without tag/digest, e.g.
  `ghcr.io/attested-delivery/app`); `image-digest` (required — `sha256:...`);
  `sbom` (boolean, default `true`); `vuln-scan` (boolean, default `true`);
  `cosign-version` (string, default `v3.0.6`).
- **Secrets:** none. **Outputs:** `provenance-verified` (`true` when the in-run
  `gh attestation verify` of SLSA provenance passed).
- **Permissions:** top-level `{}`; job `attest` needs `id-token: write`,
  `attestations: write`, `packages: write`, `contents: read`.
- **Predicates (self-signed):** `https://slsa.dev/provenance/v1` (Build L3, via
  `actions/attest-build-provenance`); CycloneDX SBOM and
  `https://in-toto.io/attestation/vulns/v0.1` via inline `cosign attest`.
- **Allow-list:** `sigstore/cosign-installer@*`, `docker/login-action`,
  `actions/attest-build-provenance` (GitHub-created), `anchore/sbom-action`,
  `anchore/scan-action`.

### `${CLAUDE_PLUGIN_ROOT}/workflows/verify-attestation.yml` — verify between hops
Verify a digest's signature + attestations, pinning the expected signing identity
to `sign-and-attest.yml`. Reused by promotion and callable before deploy. Image-only.

- **Inputs:** `image-ref` (required — `registry/repo@sha256:...`);
  `attestation-repo` (required — `owner/repo` that produced the attestation);
  `certificate-identity-regexp` (default
  `^https://github.com/attested-delivery/\.github/\.github/workflows/sign-and-attest\.yml@.*$`);
  `certificate-oidc-issuer` (default `https://token.actions.githubusercontent.com`);
  `signer-workflow` (default
  `attested-delivery/.github/.github/workflows/sign-and-attest.yml`);
  `require-sbom` (boolean, default `true`); `aws-role-arn` (default `""` — if set,
  assume the role and log into ECR before verifying); `aws-region` (default
  `us-east-1`).
- **Secrets:** none. **Outputs:** none.
- **Permissions:** top-level `{}`; job `verify` needs `id-token: write`,
  `contents: read`, `packages: read`, `attestations: read`.
- **Predicate:** none (consumes attestations from `sign-and-attest.yml`).
- **Allow-list:** `aws-actions/configure-aws-credentials`,
  `aws-actions/amazon-ecr-login` (only when `aws-role-arn` is set),
  `docker/login-action`, `sigstore/cosign-installer@*`.

---

## The quality gates (SARIF gates feed the seam)

Each SARIF gate uploads an evidence artifact and exposes `sarif-artifact` /
`sarif-filename` outputs; the caller wires those into `reusable-attest-scan.yml`
with the gate's predicate type. Predicate namespace:
`https://attested-delivery.github.io/attestations/<gate>/v1`.

### `${CLAUDE_PLUGIN_ROOT}/workflows/reusable-sast-codeql.yml` — SAST
CodeQL code scanning → SARIF 2.1.0 into the code-scanning hub.

- **Inputs:** `languages` (required — comma-separated CodeQL languages, e.g.
  `javascript-typescript,python`); `build-mode` (default `none`); `config-file`
  (default `''`); `queries` (default `''`, e.g. `security-extended`).
- **Outputs:** `sarif-artifact` = `sast-sarif`; `sarif-filename` = `results.sarif`.
- **Permissions:** job `analyze` needs `security-events: write`, `contents: read`,
  `actions: read`, `packages: read`.
- **Seam predicate:** `.../attestations/sast/v1`.
- **Allow-list:** `github/codeql-action/init` + `/analyze`, `actions/checkout`,
  `actions/upload-artifact` (all GitHub-created — confirm `github/codeql-action` is
  actually permitted, not just assumed).

### `${CLAUDE_PLUGIN_ROOT}/workflows/reusable-sca-osv.yml` — SCA
OSV-Scanner (independent second opinion) + GitHub dependency review (PR merge gate).

- **Inputs:** `fail-on-severity` (default `high` — `low|moderate|high|critical`);
  `scan-args` (default: `--recursive` and `./` — a two-line block scalar passed as
  two whitespace-separated args).
- **Outputs:** `sarif-artifact` = `OSV Scanner SARIF file`; `sarif-filename` =
  `results.sarif`.
- **Permissions:** job `osv-scan` needs `actions: read`, `contents: read`,
  `security-events: write`; job `dependency-review` needs `contents: read`,
  `pull-requests: write`.
- **Jobs:** `osv-scan` (name `osv-scanner`), `dependency-review` (name
  `dependency-review`).
- **Seam predicate:** `.../attestations/sca/v1`.
- **Allow-list:** `google/osv-scanner-action/*` (the subpath), plus GitHub-created
  `actions/dependency-review-action`, `github/codeql-action/upload-sarif`,
  `actions/checkout`, `actions/upload-artifact`.

### `${CLAUDE_PLUGIN_ROOT}/workflows/reusable-trivy.yml` — container / IaC / license
Image scan (fails on severity) plus IaC-misconfiguration + license scan (soft-fail;
the code-scanning check is the merge gate).

- **Inputs:** `image-ref` (default `''` → skip image scan); `severity` (default
  `HIGH,CRITICAL`); `scan-iac` (boolean, default `true`).
- **Outputs:** `sarif-artifact` = `iac-license-sarif`, `sarif-filename` =
  `trivy-iac-license.sarif`; and when `image-ref` set, `image-sarif-artifact` =
  `container-scan-sarif`, `image-sarif-filename` = `trivy-image.sarif`.
- **Permissions:** job `iac-license` needs `contents: read`,
  `security-events: write`, `actions: read`; job `image` adds `packages: read`.
- **Jobs:** `iac-license`, `image`.
- **Seam predicate:** `.../attestations/iac-misconfig/v1` (IaC) and the
  container-scan predicate the caller assigns for the image SARIF.
- **Allow-list:** `aquasecurity/trivy-action` (**release-critical** — a caller's
  release fails without it), plus GitHub-created actions.

### `${CLAUDE_PLUGIN_ROOT}/workflows/reusable-checkov.yml` — IaC policy
Checkov graph-based IaC policy-as-code; complements Trivy. **Needs no allow-list
entry** — installs Checkov via `pip` and uses only GitHub-created actions.

- **Inputs:** `directory` (default `.`); `framework` (default `terraform`);
  `checkov-version` (default `3.2.524` — pinned, no range).
- **Outputs:** `sarif-artifact` = `iac-policy-sarif`; `sarif-filename` =
  `checkov-iac-policy.sarif`.
- **Permissions:** job `iac-policy` needs `contents: read`, `security-events: write`,
  `actions: read`.
- **Seam predicate:** `.../attestations/iac-policy/v1`.
- **Allow-list:** none (all actions GitHub-created).

### `${CLAUDE_PLUGIN_ROOT}/workflows/reusable-scorecard.yml` — posture
OpenSSF Scorecard heuristics (0–10) → SARIF; optionally publishes to the OpenSSF
API. A repo-level posture signal, not an artifact verdict.

- **Inputs:** `publish-results` (boolean, default `true` — public repos only).
- **Outputs:** `sarif-artifact` = `scorecard-sarif`; `sarif-filename` =
  `scorecard.sarif`.
- **Permissions:** job `analysis` needs `security-events: write`, `id-token: write`,
  `contents: read`, `actions: read`.
- **Seam predicate:** `.../attestations/scorecard/v1`.
- **Allow-list:** `ossf/scorecard-action`, plus GitHub-created actions.

### `${CLAUDE_PLUGIN_ROOT}/workflows/reusable-vex.yml` — OpenVEX disposition (self-signs)
Record per-vulnerability disposition and sign it as an OpenVEX attestation bound to
the artifact digest, so the deploy gate can enforce "no UNDISPOSITIONED
high/critical" rather than "zero findings".

- **Inputs:** `subject-name` (required); `subject-digest` (required, `sha256:...`);
  `vex-path` (default `.vex/openvex.json`); `vexctl-version` (default `v0.4.1`).
- **Secrets:** none. **Outputs:** none.
- **Permissions:** job `attest-vex` needs `id-token: write`, `attestations: write`,
  `contents: read`.
- **Predicate (self-signed):** `https://openvex.dev/ns/v0.2.0` — verify with
  `--signer-workflow .../reusable-vex.yml`, not the seam.
- **Allow-list:** GitHub-created `actions/setup-go`, `actions/attest`,
  `actions/checkout`.

### `${CLAUDE_PLUGIN_ROOT}/workflows/reusable-k6.yml` — load/perf (opt-in, self-signs)
Grafana k6 load test; the gate is k6's thresholds. Optionally signs the JSON
summary as a custom performance attestation.

- **Inputs:** `script-path` (required); `attest` (boolean, default `false`);
  `subject-name` / `subject-digest` (default `''`, required when `attest: true`).
- **Secrets:** none. **Outputs:** none.
- **Permissions:** job `load` needs `id-token: write`, `attestations: write`,
  `contents: read`.
- **Predicate (self-signed when `attest: true`):**
  `.../attestations/k6-load/v1`.
- **Allow-list:** `grafana/setup-k6-action`, `grafana/run-k6-action`, plus
  GitHub-created actions.

### `${CLAUDE_PLUGIN_ROOT}/workflows/reusable-zap.yml` — DAST (opt-in)
OWASP ZAP full scan (spider + active) against a running target; uploads the JSON
report for the seam.

- **Inputs:** `target` (required — URL of the running target); `fail-action`
  (boolean, default `true`); `cmd-options` (default `-a`).
- **Outputs:** `report-artifact` = `dast-report`; `report-filename` =
  `report_json.json`.
- **Permissions:** job `dast` needs `contents: read` (no signing perms — it relies
  on the seam).
- **Seam predicate:** `.../attestations/dast/v1`.
- **Allow-list:** `zaproxy/action-full-scan`, plus GitHub-created
  `actions/upload-artifact`.

### `${CLAUDE_PLUGIN_ROOT}/workflows/reusable-secrets.yml` — secret scanning
Gitleaks (soft-fail SARIF → the gate) **and** TruffleHog (verified-only, **hard-fail**
on a confirmed live secret — a verified credential is not advisory). Both install as
checksum-verified release binaries.

- **Inputs:** `directory` (default `.`); `gitleaks-version` (default `8.30.1`);
  `trufflehog-version` (default `3.95.6`); `fail-on-verified` (boolean, default `true`).
- **Outputs:** `sarif-artifact` = `secrets-sarif`; `sarif-filename` = `gitleaks.sarif`.
- **Permissions:** job `secrets` needs `contents: read`, `security-events: write`,
  `actions: read`.
- **Seam predicate:** `.../attestations/secrets/v1` (the Gitleaks SARIF). A named gate
  in the org's 12-gate map.
- **Allow-list:** none (both tools are checksum-verified binaries; GitHub-created
  actions only).

### `${CLAUDE_PLUGIN_ROOT}/workflows/reusable-semgrep.yml` — SAST (source code)
Semgrep static analysis of bundled MCP-server / plugin source (command injection,
eval, unsafe deserialization, …). Soft-fail; complements CodeQL.

- **Inputs:** `directory` (default `.`); `config` (default
  `p/security-audit p/secrets p/command-injection`); `semgrep-version` (default `1.139.0`).
- **Outputs:** `sarif-artifact` = `sast-code-sarif`; `sarif-filename` = `semgrep.sarif`.
- **Permissions:** job `sast-code` needs `contents: read`, `security-events: write`,
  `actions: read`.
- **Seam predicate:** `.../attestations/semgrep/v1`.
- **Allow-list:** none (pip-installed in an isolated venv; GitHub-created actions).

### `${CLAUDE_PLUGIN_ROOT}/workflows/reusable-shellcheck.yml` — SAST (shell hooks)
Red Hat Differential ShellCheck (full-tree) over plugin hook scripts → native SARIF,
re-exposed for the seam.

- **Inputs:** `strict-on-push` (boolean, default `false`).
- **Outputs:** `sarif-artifact` = `sast-hooks-sarif`; `sarif-filename` = `shellcheck.sarif`.
- **Permissions:** job `sast-hooks` needs `contents: read`, `security-events: write`.
- **Seam predicate:** `.../attestations/shellcheck/v1`.
- **Allow-list:** **`redhat-plumbers-in-action/differential-shellcheck@*`** (the action
  is third-party — add it before a caller runs this gate).

### `${CLAUDE_PLUGIN_ROOT}/workflows/reusable-manifest-review.yml` — manifest integrity
Reviews the marketplace catalog and each plugin manifest for structural invariants
(external sources SHA-pinned, name not Anthropic-reserved, required fields present) →
SARIF. Pure stdlib Python; soft-fail.

- **Inputs:** `directory` (default `.`).
- **Outputs:** `sarif-artifact` = `manifest-sarif`; `sarif-filename` = `manifest-review.sarif`.
- **Permissions:** job `manifest-review` needs `contents: read`, `security-events: write`,
  `actions: read`.
- **Seam predicate:** `.../attestations/manifest/v1`.
- **Allow-list:** none (pure stdlib Python; GitHub-created actions).

### `${CLAUDE_PLUGIN_ROOT}/workflows/reusable-cosign-sign.yml` — keyless blob signing
Sign a plain **blob** (e.g. a `marketplace.json` catalog, which is not a registry
package) with Sigstore cosign keyless signing, and verify the bundle back in-run
(fail-closed). Consumers re-verify with `cosign verify-blob`.

- **Inputs:** `blob-path` (required); `cosign-version` (default `v3.1.1`).
- **Secrets:** none. **Outputs:** `bundle-artifact` = `cosign-bundle`; `bundle-filename`
  = the produced `<blob>.cosign.bundle`; `certificate-identity` = the regex matching the
  keyless signer identity (for `cosign verify-blob` by consumers).
- **Permissions:** job `cosign-sign` needs `id-token: write`, `contents: read`.
- **Predicate:** none — this is a blob signer, not a SARIF gate. The Fulcio cert SAN is
  this signer workflow; verify with `cosign verify-blob --certificate-identity-regexp`.
- **Allow-list:** **`sigstore/cosign-installer@*`**.
