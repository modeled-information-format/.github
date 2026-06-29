# Dependabot Auto-Merge Runbook — Hands-Off Patch Updates

This runbook defines how every `modeled-information-format` repo **auto-merges
Dependabot patch updates** once their required checks are green, and how to roll
the mechanism out to a repo. It is the required posture for low-risk dependency
hygiene: a patch bump that passes CI merges itself; minor and major bumps stay
manual.

## Why it's needed

Passing Dependabot PRs do **not** merge on their own. Three things block them,
and all three must be addressed together (diagnosed on `.github` #18–#21):

1. `allow_auto_merge` is off by default — GitHub's auto-merge can't be enabled.
2. Nothing requests auto-merge — green checks never merge a PR by themselves.
3. Branch protection requires **1 approving review**, and Dependabot never
   receives one.

## Mechanics it builds on (do not duplicate here)

- The reusable workflow:
  `.github/workflows/reusable-dependabot-automerge.yml` (this repo) — the single
  implementation; see the [workflow catalog](../../.github/skills/attested-delivery/references/workflow-catalog.md).
- The per-repo thin caller: `.github/workflows/dependabot-automerge.yml`.
- The settings apply script:
  `docs/onboarding/org/dependabot-automerge-settings.sh` (enables
  `allow_auto_merge`, then delegates to `branch-protection.sh`).
- Branch protection itself: [branch-protection-runbook.md](branch-protection-runbook.md).
- The org CI App identity (`vars.MIF_CI_CLIENT_APP_ID`) — see `RUNBOOK.md`.

## How it works

| Element | Choice | Why |
| --- | --- | --- |
| Scope | **patch only** | Lowest risk; minor/major keep a human in the loop. |
| Gate | `dependabot/fetch-metadata` | Reads the PR's semver `update-type`. |
| Approver | **org CI App** | Dependabot can't approve its own PR; the App's review satisfies the required 1 review. |
| Trigger | `pull_request_target` | Dependabot's own `pull_request` runs get a read-only token with **no secrets**, so the App key is unreachable there. |
| Merge | `gh pr merge --auto --squash` | Waits for required checks + up-to-date branch, then merges. |

**Security.** Running in the privileged `pull_request_target` context is safe
here because the job **never checks out or executes PR head code** — it only
reads metadata and calls `gh` (approve/merge). Do not add a `checkout` of the PR
head to this workflow.

**Actions bumps stay pinned.** Dependabot's `github-actions` updates remain
SHA-pinned and are still gated by `pin-check`; auto-merge does not relax that.

## Roll out to a repo

```bash
# 1. Add the thin caller (worktree + PR), pinned to the reusable's SHA on .github main:
#    .github/workflows/dependabot-automerge.yml
#      on: pull_request_target { types: [opened, synchronize, reopened] }
#      if: github.actor == 'dependabot[bot]'
#      uses: modeled-information-format/.github/.github/workflows/reusable-dependabot-automerge.yml@<sha>
#      with: { update-types: patch }
#      secrets: { app-private-key: ${{ secrets.MIF_CI_CLIENT_APP_PRIVATE_KEY }} }

# 2. Apply the settings (allow_auto_merge + branch protection, with the repo's contexts):
GH_TOKEN=<admin-token> \
  bash docs/onboarding/org/dependabot-automerge-settings.sh <owner/repo> main "<ctx>" "<ctx>" ...
```

Discover a repo's required-check contexts exactly as in the
[branch-protection runbook](branch-protection-runbook.md#discover-a-repos-contexts).

## Verify

```bash
# allow_auto_merge is on:
gh api "/repos/<owner/repo>" --jq '.allow_auto_merge'

# Then on a live patch Dependabot PR, expect: the App posts an APPROVED review and
# auto-merge is enabled; on existing PRs trigger a re-run with "@dependabot rebase".
gh pr view <num> --repo <owner/repo> --json reviewDecision,autoMergeRequest \
  --jq '{review: .reviewDecision, autoMerge: (.autoMergeRequest != null)}'
```

A **patch** PR auto-approves + auto-merges once required checks are green; a
**minor/major** PR stays open awaiting manual merge (expected).

## Scope & exclusions

- **In scope:** every active org repo with CI. Roll out is tracked under epic
  `.github#23`, one sub-issue per repo.
- **Deferred N/A:** empty repos (no commits/branch) and private template repos —
  no Dependabot/CI to gate yet; revisit when they have content.

## Prerequisites

The org CI App (`modeled-information-format-ci`) must have `pull_requests: write`
and `contents: write` and be installed org-wide (it is — verify with
`GET /app` via an App JWT if in doubt). Its approval is what satisfies branch
protection's required review; do not lower `required_approving_review_count` to 0
to work around a missing App.
