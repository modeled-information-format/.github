---
id: bfe8e980-3ea7-47e8-af8c-191a24114da1
type: procedural
created: 2026-07-04T10:00:07-04:00
namespace: _procedural/runbooks
title: "Pages Deploy Runbook"
tags:
  - runbook
  - pages
---

# Pages Deploy Runbook — Publishing the Org's GitHub Pages Sites

This runbook covers how every `modeled-information-format` project site reaches
production, how to trigger a deploy without cutting a release, and a gap this
org hit twice: a merge to `main` that never reached the live site.

## Two deploy shapes in this org

**Composed sites** — the org root splash and `/docs` are not built by their own
repos. `modeled-information-format.github.io`'s `deploy.yml` checks out
`.github` (for `index.html`, the root landing page) and `doc-site` (for
`/docs`, built with `npm run build`) fresh at deploy time and assembles both
under one Pages deployment. Neither `.github` nor `doc-site` has its own
`deploy.yml` — there is nothing in either repo for `workflow_dispatch` to run
against directly.

**Self-deploying sites** — `mif-rs`, `ontologies`, `mif-docs-plugin`,
`claude-code-plugins`, `structured-madr`, and `research-harness-template` each
build and publish their own Pages site directly, with their own `deploy.yml`.

## Triggering a deploy without a release

Every `deploy.yml` in this org (self-deploying sites and the composed
`.io` site alike) triggers on **both** a push to `main` and
`workflow_dispatch`. None require a tag or a published GitHub Release. To
force a redeploy of the current `main` on demand:

```bash
gh workflow run deploy.yml --repo modeled-information-format/<repo>
```

For the composed root/`/docs` site, `<repo>` is always
`modeled-information-format.github.io` — dispatching `.github` or `doc-site`
themselves has no deploy workflow to trigger.

## The dormant-hook gap

A push to `main` on a self-deploying site's own repo triggers that repo's own
`deploy.yml` directly — no extra step needed. A push to `main` on `.github` or
`doc-site`, by contrast, does **not** automatically trigger the `.io` repo's
`deploy.yml`, because that workflow only listens for a push to *its own*
`main`, `workflow_dispatch`, or a `repository_dispatch` of type
`source-updated`. Without something firing that dispatch, a merge to
`.github` or `doc-site` sits published on `main` but never reaches the live
site until someone remembers to run the manual `workflow_dispatch` above.

`research-harness-template` hit this first and fixed it: its
`.github/workflows/docs.yml` runs a `notify-deploy` job after a green build on
every push to `main`, minting a short-lived GitHub App token (the `pages` App,
scoped only to `modeled-information-format.github.io`, `contents: write`) and
firing the dispatch:

```bash
gh api --method POST \
  "repos/modeled-information-format/modeled-information-format.github.io/dispatches" \
  -f event_type=source-updated
```

`.github` and `doc-site` carry the identical `notify-deploy` job in their own
`ci.yml` (added 2026-07-04, after a root-splash content change sat merged and
unpublished until this was traced). Any new repo whose content feeds the
composed `.io` site needs this same job — copy it from `research-harness-template`'s
`docs.yml` or either of the two `ci.yml` files above, adjusting only the
`needs:` job it waits on.

## Verify a deploy actually ran

```bash
gh run list --repo modeled-information-format/modeled-information-format.github.io \
  --workflow=deploy.yml --limit=1 --json databaseId,status,event,createdAt
```

`event` shows `push`, `workflow_dispatch`, or `repository_dispatch` depending
on what triggered it.
