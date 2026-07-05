# Attested catalog-updater

A central, **verify-first** analog to Dependabot for Claude Code plugin
marketplaces in this org. Dependabot can't update a marketplace catalog — no
ecosystem parses the custom `git-subdir` + 40-char `sha` pins inside
`.claude-plugin/marketplace.json`, and submodule tracking follows branch HEAD,
not attested release tags. So this is the org's own mechanism.

It **fetches by release**, **verifies the candidate release's attestations (the
subjects) before proposing a re-pin**, and opens a **zero-touch auto-merge PR**
whose body carries the full attestation evidence. It inverts Dependabot: verify
first, propose only releases that already prove their attestations — *the thing
you verified is the thing that runs.*

## Pieces

| Path | Role |
| --- | --- |
| [`.github/workflows/plugin-catalog-update-hub.yml`](../.github/workflows/plugin-catalog-update-hub.yml) | Scheduled hub: discover target marketplaces → matrix → per-repo run |
| [`.github/actions/plugin-catalog-update/`](../.github/actions/plugin-catalog-update/) | Composite action + engine (`catalog_update.py`): resolve release, verify-first, re-pin, PR, auto-merge. Shared `verify` mode is reused by `catalog-admission` |
| [`deny-list.yaml`](./deny-list.yaml) | Optional safety valve — repos the hub must never touch |

## How a marketplace opts in

**Opt-in = install the org `catalog` App on the repo** (ADR-011; with
`contents: write` + `pull-requests: write` + `actions: write`, per `auth/apps.json`). Discovery is App-install-scoped: the
hub updates exactly the repos the App can access that contain a
`.claude-plugin/marketplace.json`, minus anything in `deny-list.yaml`. There is no
registry file to maintain — the App-installation set *is* the opt-in, so the hub
can never reach beyond where its credential already has access.

Opt out by uninstalling the App, or by adding the `owner/repo` to
`deny-list.yaml` (the safety valve when the App is installed org-wide).

## What it does, per external entry

1. Resolve the source repo's **latest release** (`releases/latest`); skip entries
   with no release.
2. Dereference the tag to a **commit sha** (`commits/<tag>` — handles annotated
   tags); skip if unchanged.
3. **Verify the release's attestations fail-closed** (`gh attestation verify`).
   Only a release whose **every** required predicate verifies advances; a release
   that fails is skipped and logged, never re-pinned.
4. **Re-pin** `source.sha` + `source.ref` (surgical text edit — formatting
   preserved).
5. **Open an auto-merge PR** in the target repo (`deps/external-plugin/<name>`)
   with the full attestation evidence in the body.

The target repo's fail-closed `catalog-admission` gate re-verifies on the PR and
is the merge control; the PR auto-merges once it and the required gates are green.

## Required predicates

Default (v1): SLSA build provenance (`https://slsa.dev/provenance/v1`, verified by
`--repo`). Pass `predicate-types` (one `"<uri> [signer-workflow]"` per line) to
require more — e.g. CycloneDX SBOM and the seam-signed gate verdicts
(`reusable-attest-scan.yml` signer). The same set should be required in the
target's `catalog-admission` so the hub and the gate agree.

## Owner setup

The hub reads the `catalog` App's **client id** from an **org variable** and its
private key from an **org secret** (the client id is a public identifier, the key is
not). `actions/create-github-app-token` takes `client-id` (the `app-id` input is
deprecated). Provision both org-wide (visibility `all`). `gh variable/secret set
--org` does not work for this org — use the REST API with the org-admin token (see
[the five-app provisioning guide](../docs/onboarding/app/five-app-provisioning.md)):

```bash
TOK=<org-admin token>
# App client id (public identifier, e.g. Iv23li...) — org variable, visibility all
# Idempotent: update if it exists, else create.
NAME=CATALOG_CLIENT_APP_ID VALUE=Iv23li...
curl -fsS -X PATCH -H "Authorization: Bearer $TOK" -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/orgs/modeled-information-format/actions/variables/$NAME" \
  -d "{\"value\":\"$VALUE\",\"visibility\":\"all\"}" \
  || curl -fsS -X POST -H "Authorization: Bearer $TOK" -H "X-GitHub-Api-Version: 2022-11-28" \
    https://api.github.com/orgs/modeled-information-format/actions/variables \
    -d "{\"name\":\"$NAME\",\"value\":\"$VALUE\",\"visibility\":\"all\"}"

# App private key -> org secret CATALOG_CLIENT_APP_PRIVATE_KEY: GET the org public key,
# sealed-box encrypt the .pem, PUT { encrypted_value, key_id, visibility:"all" }.
```

Also:

- Allow-list `actions/create-github-app-token` (it is `actions/*`, intended-allowed
  — confirm, don't assume).
- The `catalog` App needs **contents** (write), **pull requests** (write),
  **actions** (write, for repository_dispatch/workflow_dispatch to plugin repos),
  and **metadata** (read, to enumerate `installation/repositories`).
- **Zero-touch ruleset bypass:** on each target repo, let the App actor bypass the
  required human review on `deps/external-plugin/*` PRs while keeping
  `catalog-admission` + the gates as required checks — so the fail-closed gate is
  the sole merge control.

## Dry run

```bash
gh workflow run plugin-catalog-update-hub.yml -f dry-run=true
```

Resolves + verifies + renders the PR body to the run log, opening and merging
nothing.
