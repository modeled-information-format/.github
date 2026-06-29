#!/usr/bin/env bash
# Apply the per-repo prerequisites for Dependabot auto-merge. These are repo
# SETTINGS (no file form); this script is the auditable, idempotent source of
# truth, applied via the admin API. Pair it with the per-repo caller workflow
# .github/workflows/dependabot-automerge.yml and the reusable
# reusable-dependabot-automerge.yml.
#
# It does two things:
#   1) allow_auto_merge = true        (so `gh pr merge --auto` works at all)
#   2) org-standard branch protection (delegates to the sibling branch-protection.sh):
#      1 review, strict + linear history, conversation resolution, and the repo's
#      required check contexts. The App's approval satisfies the required review.
#
# REQUIRES: a gh token with admin on the target repo (GH_TOKEN or `gh auth`).
# Idempotent: re-running is safe.
#
# Usage:
#   bash dependabot-automerge-settings.sh <owner/repo> <branch> [required-check-context ...]
#
# Example (.github main):
#   bash dependabot-automerge-settings.sh modeled-information-format/.github main \
#     "actionlint / actionlint"
set -euo pipefail

REPO="${1:?usage: dependabot-automerge-settings.sh <owner/repo> <branch> [context ...]}"
BRANCH="${2:?usage: dependabot-automerge-settings.sh <owner/repo> <branch> [context ...]}"
shift 2

echo "== Enabling allow_auto_merge on $REPO =="
gh api -X PATCH "/repos/$REPO" -F allow_auto_merge=true >/dev/null

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$DIR/branch-protection.sh" "$REPO" "$BRANCH" "$@"

echo "== Dependabot auto-merge prerequisites applied to $REPO@$BRANCH =="
