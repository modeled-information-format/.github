#!/usr/bin/env bash
# Apply the org-standard branch protection to a repo's default branch.
#
# Complements org/harden.sh (which sets ORG-level posture). This sets the
# per-REPO default-branch protection so every org repo enforces the same gate:
# PR-only changes, a review, an up-to-date branch, and ALL of the repo's
# always-on PR checks green before merge.
#
# REQUIRES: a gh token with admin on the target repo (org owners have this):
#     gh auth refresh -h github.com -s admin:org
#
# Idempotent: a declarative PUT of desired state. Re-running is safe.
#
# Usage:
#   bash branch-protection.sh <owner/repo> <branch> [required-check-context ...]
#   # Discover a repo's always-on PR contexts (paste them as args):
#   #   gh api "/repos/<owner/repo>/commits/<a-recent-PR-head-sha>/check-runs" \
#   #     --jq '.check_runs[] | select(.conclusion!="skipped") | .name' | sort -u
#   # Exclude any context that is skipped or path-filtered on some PRs — a
#   # required check that does not report on a PR blocks the merge forever.
#
# Example (MIF main, the worked reference set):
#   bash branch-protection.sh modeled-information-format/MIF main \
#     "codeql / analyze" "semgrep / sast-code" "trivy / iac-license" \
#     "checkov / iac-policy" "sca / osv-scanner" "sca / dependency-review" \
#     "secrets / secrets" "shellcheck / sast-hooks" "pin-check / pin-check" \
#     "actionlint / actionlint" "validate-schema-files" \
#     "OKF Conformance + Lossless Round-Trip" \
#     "Validate JSON-LD Projection Against Schema" \
#     "Validate Ontology Files" "Build Docs Site (Astro)"
set -euo pipefail

REPO="${1:?usage: branch-protection.sh <owner/repo> <branch> [context ...]}"
BRANCH="${2:?usage: branch-protection.sh <owner/repo> <branch> [context ...]}"
shift 2
CONTEXTS=("$@")

# Build the required-status-checks contexts JSON array from the args.
contexts_json="$(printf '%s\n' "${CONTEXTS[@]:-}" | python3 -c '
import json,sys
print(json.dumps([l for l in sys.stdin.read().splitlines() if l.strip()]))')"

echo "== Applying org-standard branch protection to $REPO@$BRANCH =="
echo "   required checks: $(printf '%s\n' "${CONTEXTS[@]:-}" | grep -c . || true)"

# Enable repo-level auto-merge so `gh pr merge --auto` works (e.g. the catalog
# update hub and Dependabot open auto-merge PRs). Idempotent.
echo "== Enabling allow_auto_merge on $REPO =="
gh api -X PATCH "/repos/$REPO" -F allow_auto_merge=true >/dev/null

# The org CI App authors zero-touch re-pin PRs (catalog update hub) and cannot
# approve its own PR, so it is allowed to BYPASS the required review. Human PRs
# still need a review; the required status checks (incl. catalog-admission) remain
# the gate for the App's auto-merge.
gh api -X PUT "/repos/$REPO/branches/$BRANCH/protection" \
  -H "Accept: application/vnd.github+json" \
  --input - >/dev/null <<JSON
{
  "required_status_checks": { "strict": true, "contexts": ${contexts_json} },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "bypass_pull_request_allowances": {
      "users": [],
      "teams": [],
      "apps": ["modeled-information-format-ci"]
    }
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON

echo "   -> applied. Current state:"
gh api "/repos/$REPO/branches/$BRANCH/protection" --jq '{
  require_pr: (.required_pull_request_reviews != null),
  approvals: .required_pull_request_reviews.required_approving_review_count,
  review_bypass_apps: [.required_pull_request_reviews.bypass_pull_request_allowances.apps[]?.slug],
  strict_up_to_date: .required_status_checks.strict,
  required_checks: (.required_status_checks.contexts | length),
  enforce_admins: .enforce_admins.enabled,
  force_push: .allow_force_pushes.enabled,
  deletions: .allow_deletions.enabled,
  linear_history: .required_linear_history.enabled,
  conversation_resolution: .required_conversation_resolution.enabled
}'
gh api "/repos/$REPO" --jq '{allow_auto_merge}'
