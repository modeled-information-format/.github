---
id: reference-plugin-dependency-tags
type: semantic
created: 2026-07-06T19:36:06Z
modified: 2026-07-06T19:36:06Z
namespace: reference/plugin-dependencies
title: "Plugin Dependency Tags"
tags:
  - claude-code-plugins
  - marketplace
  - dependency-resolution
  - semver
  - git-tags
temporal:
  '@type': TemporalMetadata
  validFrom: '2026-07-06T19:36:06Z'
  recordedAt: '2026-07-06T19:36:06Z'
provenance:
  '@type': Provenance
  sourceType: system_generated
  trustLevel: verified
  wasDerivedFrom:
    '@id': 'urn:mif:incident:mif-docs-github-sdlc-planning-dependency-resolution-failure'
    '@type': prov:Entity
citations:
  - '@type': Citation
    citationType: tool
    citationRole: source
    title: attest-release.yml source (this repo's own automation)
    url: https://github.com/modeled-information-format/.github/blob/main/.github/workflows/attest-release.yml
relationships:
  - type: relates-to
    target: /procedural/runbooks/release-runbook.md
---

# Plugin Dependency Tags

## The mechanism

When one Claude Code plugin's `plugin.json` declares a dependency on another
plugin by **semver range** (e.g. `"version": "^0.3.1"`, rather than a pinned
SHA), Claude Code resolves that range by running `git ls-remote --tags`
against the dependency's own repository. It only considers tags shaped:

```text
{pluginName}--v{version}
```

where `{pluginName}` is the `name` field from the dependency's own
`plugin.json` — **not** the marketplace catalog entry name (the two can
differ; see the cross-marketplace example below), and not the repo name. A
bare `vX.Y.Z` release tag, the shape most repos already cut for their own
releases, is invisible to this resolution — it does not match the pattern
and Claude Code will report `no git tag satisfying <range>` even when the
marketplace catalog's SHA pin is entirely correct and the release itself is
fine.

This was discovered via a real break: `github-sdlc-planning@github-sdlc-plugins`
declares a dependency on `mif-docs@modeled-information-format` by semver
range. Installing it failed with exactly that error until the
`mif-docs--v0.3.1` tag was created — the catalog pin was never the problem.

## Why this is a second tag, not the release tag

Most repos in this org cut one release tag per version (`vX.Y.Z`), or one
shared tag across several plugins in a monorepo-style plugin repo. The
dependency-resolution tag is a **separate, purpose-built tag**, needed only
when another plugin might declare a dependency on this one by version range
instead of an exact SHA pin. A repo with no inbound semver-range dependents
does not strictly need it, but every repo in this org that ships a plugin
creates it anyway, since a future dependent's needs are not knowable in
advance and backfilling after the fact requires locating the exact historical
release commit (see the drift gotcha below).

## Creating it manually

```sh
claude plugin tag --push [path-to-plugin-if-monorepo]
```

The `claude` CLI's `plugin tag` subcommand reads the target `plugin.json`'s
`name` and `version`, validates that entry against the marketplace's
`marketplace.json`, then creates and pushes an annotated tag
`{name}--v{version}` at the current commit. Omit the path argument for a
single-plugin repo; pass the plugin's subdirectory for a repo that hosts
several plugins (e.g. this org's `gdlc` repo, which tags each of its seven
plugins independently at the same version).

**Drift gotcha:** `claude plugin tag --push` tags whatever commit is
currently checked out. If `main` has moved past the actual release commit —
more commits landed after the release without a `plugin.json` version bump —
running the command against current `HEAD` silently points dependents at
unreviewed, unattested content that was never part of the release. Tag the
release commit specifically: check out a throwaway worktree at the release's
own `vX.Y.Z` tag (or the release commit SHA), run `claude plugin tag --push`
there, then remove the worktree. Never assume current `HEAD` is the release
commit for a repo that has had any activity since the last release.

## Automating it in a release workflow

Each repo hooks the dependency-tag push into the same workflow run that
already fires at the release commit, reusing whatever release-identity
credential that run already mints — no separate token or app is needed.

- **This repo (`.github`, plugin `attested-delivery`)**: `attest-release.yml`
  triggers on `release: types: [published]`. Its `package` job already
  resolves the release tag and checks out that exact commit before doing
  anything else; a step immediately after checkout reads `name` and
  `version` from `.github/.claude-plugin/plugin.json` with `jq`, then creates
  the tag object and ref via the GitHub API (`git/tags` then `git/refs`)
  using the job's own `GITHUB_TOKEN` (`contents: write`, already granted for
  uploading release assets — no additional permission or app-token minting
  required). The step is guarded to run only on `github.event_name ==
  'release'` (the `workflow_dispatch` path re-attests an already-released
  tag and must not attempt to re-create it) and additionally checks whether
  the tag ref already exists before creating it, so a retried or re-dispatched
  run is a no-op rather than a failure. It also fails loudly, rather than
  silently mistagging, if `plugin.json`'s `version` doesn't match the release
  tag being attested (a forgotten version bump) or if `name`/`version` can't
  be read at all.
- **`mif-docs-plugin`** (plugin `mif-docs`) and **`gdlc`** (seven plugins)
  follow the same shape in their own `release.yml`: the job that already runs
  at the release commit gains a step that reads the relevant `plugin.json`
  (once per plugin, for `gdlc`'s seven), computes `{name}--v{version}`, and
  pushes the tag using whichever token that workflow already has for the
  release (an app-minted installation token where the workflow already mints
  one, or `GITHUB_TOKEN` where that already suffices, mirroring whatever
  identity the workflow was already using to publish the release itself).

The general pattern to replicate in a new repo: find the step in the
release/attest workflow that is already checked out at the release commit and
already holds a token capable of writing to the repo, and add the tag-create
step there — do not mint a new credential or add a new trigger just for this.

## Cross-marketplace dependencies

A plugin dependency across two *different* marketplaces needs one more piece
before tag resolution is ever reached: the dependent's marketplace must list
the dependency's marketplace under `allowCrossMarketplaceDependenciesOn` in
its own `marketplace.json`, or installation fails with a separate
`cross-marketplace` error first. For example, `gdlc`'s
`.claude-plugin/marketplace.json` declares:

```json
"allowCrossMarketplaceDependenciesOn": ["modeled-information-format"]
```

to permit its plugins to depend on plugins cataloged in the
`modeled-information-format` marketplace (such as `mif-docs`). Both this
allow-list entry AND the `{pluginName}--v{version}` tag must be in place for
a cross-marketplace semver-range dependency to resolve.

## Currently-registered dependency tags (verified against live git tags)

| Repo | Plugin | Tag |
| --- | --- | --- |
| `.github` | `attested-delivery` | `attested-delivery--v0.1.0` |
| `mif-docs-plugin` | `mif-docs` | `mif-docs--v0.3.1` |
| `gdlc` | `github-sdlc-planning` | `github-sdlc-planning--v0.4.0` |
| `gdlc` | `github-pull-requests` | `github-pull-requests--v0.4.0` |
| `gdlc` | `github-repo-config` | `github-repo-config--v0.4.0` |
| `gdlc` | `github-insights` | `github-insights--v0.4.0` |
| `gdlc` | `github-packages` | `github-packages--v0.4.0` |
| `gdlc` | `github-org-identity` | `github-org-identity--v0.4.0` |
| `gdlc` | `github-bug-capture` | `github-bug-capture--v0.4.0` |

## Related

- [Release Runbook](../runbooks/release-runbook.md) — the general org release
  process this tag is created alongside, not a replacement for it.
- `attest-release.yml` — this repo's own implementation of the automated tag
  push described above.
