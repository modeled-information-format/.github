---
id: 0a1eebf7-33fc-42ba-82fb-3bf8365bf95d
type: procedural
created: 2026-07-01T00:00:00-04:00
namespace: _procedural/runbooks
title: "OSV-Scanner Alert Runbook"
tags:
  - runbook
  - sca
  - osv
  - supply-chain
---

# OSV-Scanner Alert Runbook — Failed SCA Check or Code-Scanning Alert

This runbook covers a failed `sca` status check or a new OSV-Scanner
code-scanning alert in any repo consuming
`modeled-information-format/.github/.github/workflows/reusable-sca-osv.yml`
(currently: `MIF`, `claude-code-plugins`, `mif-repo-template`, `ontologies`,
`structured-madr`, `doc-site`, `mif-docs-plugin`, `research-harness-template`).
See [ADR-004](../adr/ADR-004-supply-chain-scanning.md) for why this gate
exists, [ADR-012](../adr/ADR-012-osv-scanner-rollout-completion.md) for its
rollout, and
[the reference doc](../reference/reusable-sca-osv.md) for the workflow's
inputs and consuming repos.

## Overview

The `sca` job runs two layers on every push and pull request: OSV-Scanner (an
independent scan against the OSV vulnerability database, uploaded as SARIF to
the repo's code-scanning hub) and `dependency-review-action` (the PR merge
gate, failing on a newly introduced dependency at or above the configured
`fail-on-severity`, default `high`). This runbook covers both failure modes:
a blocked PR and a standalone code-scanning alert.

## Prerequisites & Access

- Read access to the affected repo's **Security** tab (code-scanning alerts)
  and **Pull requests** tab (the `dependency-review` check annotation).
- `gh` CLI authenticated against the org (`gh auth status`).
- For remediation: write access to open a branch and push a dependency bump.

## Detection

Two independent signals, from the two layers:

1. **Blocked PR** — the `sca` / `dependency-review` status check on a pull
   request shows failed. Confirm with:

   ```bash
   gh pr checks <PR-NUMBER> --repo modeled-information-format/<REPO>
   ```

   A failing `dependency-review` line means the PR introduces a dependency at
   or above `fail-on-severity`, or a disallowed license.

2. **Code-scanning alert** — a new alert appears in the repo's **Security ->
   Code scanning** tab, independent of any open PR (OSV-Scanner runs on every
   push to the default branch too, not only PRs). Confirm the alert's tool is
   OSV-Scanner, not a different scanner sharing the same hub (SAST/CodeQL,
   Trivy, Checkov, Gitleaks/TruffleHog all upload SARIF to the same tab):

   ```bash
   gh api repos/modeled-information-format/<REPO>/code-scanning/alerts \
     --jq '.[] | select(.tool.name == "osv-scanner") | {number, rule: .rule.id, severity: .rule.security_severity_level, state}'
   ```

## Diagnosis

1. **Read the `dependency-review` annotation** (blocked-PR case) or the
   **alert detail** (code-scanning case) for the affected package name,
   installed version, severity, and advisory id (GHSA-xxxx or OSV id):

   ```bash
   gh api repos/modeled-information-format/<REPO>/code-scanning/alerts/<ALERT-NUMBER> \
     --jq '{rule: .rule.id, severity: .rule.security_severity_level, description: .rule.description}'
   ```

2. **Open the advisory** to read the affected version range and the patched
   version:

   ```bash
   gh api /advisories/<GHSA-ID> --jq '{summary, severity, vulnerabilities: [.vulnerabilities[] | {package: .package.name, vulnerable_range: .vulnerable_version_range, patched: .first_patched_version.identifier}]}'
   ```

3. **Determine direct vs. transitive.** Check whether the package appears in
   the repo's `package.json` `dependencies`/`devDependencies` (direct) or only
   in `package-lock.json` (transitive):

   ```bash
   grep -n "\"<PACKAGE-NAME>\"" package.json
   ```

   A hit in `package.json` means direct; no hit means transitive, pulled in by
   one of the direct dependencies.

## Remediation

1. **Direct dependency, patch available** — bump to the patched version:

   ```bash
   npm install <PACKAGE-NAME>@<PATCHED-VERSION>
   npm run lint --if-present && npm test --if-present
   ```

   Expected result: `package-lock.json` updates to the patched version; local
   test/lint gates (if present) still pass.

2. **Transitive dependency, patch available upstream** — check whether a
   newer release of the direct dependency that pulls it in already exists:

   ```bash
   npm ls <PACKAGE-NAME>
   npm outdated <DIRECT-DEPENDENCY-NAME>
   ```

   If a newer direct-dependency release resolves the transitive vulnerability,
   bump the direct dependency instead of overriding the transitive one
   directly. Only use an `overrides` (npm) or `resolutions` (yarn) field if no
   upstream release exists yet, and note the override with a comment linking
   the advisory so it is not forgotten once a real fix ships.

3. **No patch available yet** — do not silence the finding by disabling the
   gate or lowering `fail-on-severity`. This org's supply-chain layer includes
   an OpenVEX exploitability disposition step (see
   [ADR-004](../adr/ADR-004-supply-chain-scanning.md)) for exactly this case:
   disposition the specific advisory as `not_affected` (with a documented
   justification, e.g. the vulnerable code path is unreachable in this repo's
   usage) rather than suppressing the class of finding. Changing
   `fail-on-severity` is a scope change to the gate itself and requires its
   own decision (an ADR), not a per-incident workaround.

4. **Commit the fix**:

   ```bash
   git add package.json package-lock.json
   git commit -m "fix(deps): bump <PACKAGE-NAME> to <PATCHED-VERSION> (<GHSA-ID>)"
   git push
   ```

## Escalation

Escalate to the repo maintainer, do not force a merge past the gate, when:

- The advisory is disputed (e.g. the maintainer believes the CVE/GHSA is
  mis-scored or does not apply to this repo's actual usage) — the VEX
  disposition path in ADR-004 requires a maintainer's documented justification,
  not a unilateral one.
- OSV-Scanner itself appears to misbehave (a clear false positive, a tool
  crash, a SARIF upload failure unrelated to the dependency itself).
- The only available fix is a breaking major-version bump with application-
  level compatibility risk that cannot be validated by CI alone.

## Verification & Rollback

**Verification**: after pushing the fix, re-run the check:

```bash
gh pr checks <PR-NUMBER> --repo modeled-information-format/<REPO> --watch
```

Expected result: `dependency-review` and `sca` both report success. For a
standalone code-scanning alert (no open PR), confirm the alert closes on the
next scheduled or push-triggered scan:

```bash
gh api repos/modeled-information-format/<REPO>/code-scanning/alerts/<ALERT-NUMBER> --jq '.state'
```

Expected result: `state` is `fixed` or `dismissed` (with a documented VEX
disposition, if dispositioned rather than patched).

**Rollback**: if the dependency bump breaks the build (test/lint/build
failure unrelated to the vulnerability fix), revert the single commit:

```bash
git revert HEAD
git push
```

This restores the prior, vulnerable dependency version — the `sca` check will
fail again, which is the expected, safe state (blocked, not silently merged)
until a working patched version is found.
