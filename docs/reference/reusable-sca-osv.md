---
id: reference-reusable-sca-osv
type: semantic
created: 2026-07-01T00:00:00Z
modified: 2026-07-01T00:00:00Z
namespace: reference/reusable-workflows
title: "reusable-sca-osv.yml"
tags:
  - sca
  - osv
  - supply-chain
  - reusable-workflow
  - github-actions
temporal:
  '@type': TemporalMetadata
  validFrom: '2026-07-01T00:00:00Z'
  recordedAt: '2026-07-01T00:00:00Z'
provenance:
  '@type': Provenance
  sourceType: system_generated
  trustLevel: verified
  wasDerivedFrom:
    '@id': 'urn:mif:workflow:reusable-sca-osv'
    '@type': prov:Entity
citations:
  - '@type': Citation
    citationType: tool
    citationRole: source
    title: reusable-sca-osv.yml source
    url: https://github.com/modeled-information-format/.github/blob/main/.github/workflows/reusable-sca-osv.yml
  - '@type': Citation
    citationType: specification
    citationRole: methodology
    title: 'ADR-004: Supply-Chain Scanning'
    url: https://github.com/modeled-information-format/.github/blob/main/docs/adr/ADR-004-supply-chain-scanning.md
relationships:
  - type: relates-to
    target: /semantic/adr/ADR-004-supply-chain-scanning.md
  - type: relates-to
    target: /semantic/adr/ADR-012-osv-scanner-rollout-completion.md
---

# reusable-sca-osv.yml

`modeled-information-format/.github/.github/workflows/reusable-sca-osv.yml` — a
`workflow_call` reusable workflow providing software composition analysis (SCA)
via OSV-Scanner and GitHub's `dependency-review-action`.

## Synopsis

```yaml
jobs:
  sca:
    permissions:
      actions: read
      contents: read
      security-events: write
      pull-requests: write
    uses: modeled-information-format/.github/.github/workflows/reusable-sca-osv.yml@<sha>
    with:
      fail-on-severity: high
```

## Trigger

| Property | Value |
| --- | --- |
| Event | `workflow_call` |
| Direct invocation | Not supported. Called only from a consuming repo's own workflow file. |

## Inputs

| Name | Type | Default | Constraints | Description |
| --- | --- | --- | --- | --- |
| `fail-on-severity` | string | `high` | one of `low`, `moderate`, `high`, `critical` | The `dependency-review-action` threshold. A pull request introducing a dependency at or above this severity fails the check. |
| `scan-args` | string | `--recursive`\n`./` | any valid OSV-Scanner CLI arguments | Arguments passed to the OSV-Scanner invocation. |

## Required permissions (calling job)

| Permission | Level | Description |
| --- | --- | --- |
| `actions` | `read` | Read workflow run metadata. |
| `contents` | `read` | Read the repository checkout. |
| `security-events` | `write` | Upload OSV-Scanner SARIF output to the code-scanning hub. |
| `pull-requests` | `write` | Allow `dependency-review-action` to annotate the pull request. |

## Layers provided

| Layer | Tool | License | Output |
| --- | --- | --- | --- |
| Independent SCA scan | OSV-Scanner (Google) | Apache-2.0 | SARIF, uploaded to the consuming repo's code-scanning hub (Security tab) |
| PR merge gate | `dependency-review-action` (GitHub) | MIT | Pass/fail check on the pull request; fails when a PR introduces a dependency at or above `fail-on-severity`, or a disallowed license |

Dependabot alerts are a third, complementary layer. They are configured at the
repo level and are outside this workflow.

## Pinned SHA in active use

| Field | Value |
| --- | --- |
| SHA | `f83ee8058630235396f7242580570b26cf3617fa` |

## Consuming repos (as of 2026-07-01)

| Repo | Status |
| --- | --- |
| `MIF` | Consuming |
| `claude-code-plugins` | Consuming |
| `mif-repo-template` | Consuming |
| `ontologies` | Consuming |
| `structured-madr` | Consuming |
| `doc-site` | Consuming (PR open, pending review) |
| `mif-docs-plugin` | Consuming (PR open, pending review) |
| `research-harness-template` | Consuming (PR open, pending review) |
| `mnemonic-vscode` | Not consuming — tracked, deliberately excluded from the 2026-07-01 rollout |
| `design-system` | Not consuming — blocked on baseline CI setup |
| `mnemonic` | Not applicable — pure Go module, no lockfile |
| `modeled-information-format.github.io` | Not applicable — no dependency lockfile |

## Related

- [ADR-004: Supply-Chain Scanning](../adr/ADR-004-supply-chain-scanning.md) —
  established this reusable as the org's standard SCA gate.
- [ADR-012: OSV-Scanner Rollout Completion](../adr/ADR-012-osv-scanner-rollout-completion.md)
  — the 2026-07-01 decision closing the adoption gap documented above.
- `reusable-sast-codeql.yml` — the org's SAST gate.
- `reusable-trivy.yml`, `reusable-checkov.yml`, `reusable-secrets.yml`,
  `reusable-vex.yml` — the org's other supply-chain reusables.
