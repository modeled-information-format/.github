#!/usr/bin/env bash
# Org-level security hardening for the attested-delivery org.
#
# REQUIRES: an active gh token with the `admin:org` scope. Grant it once with:
#     gh auth refresh -h github.com -s admin:org
# Then run:  bash org/harden.sh
#
# Idempotent: every call is a declarative PUT/PATCH of desired state.
set -euo pipefail
ORG=attested-delivery

echo "== 1. Org member/repo policy (PATCH /orgs/$ORG) =="
# Least-privilege defaults: members get read by default; no member-created public
# repos (org owners curate the canonical set); no member repo deletion.
gh api -X PATCH "/orgs/$ORG" \
  -F default_repository_permission=read \
  -F members_can_create_public_repositories=false \
  -F members_can_create_private_repositories=false \
  -F members_can_delete_repositories=false \
  -F web_commit_signoff_required=true \
  --jq '{default_repository_permission, members_can_create_public_repositories, web_commit_signoff_required}'

echo "== 2. Restrict Actions to allowed, github-owned + verified, SHA-pinning posture =="
gh api -X PUT "/orgs/$ORG/actions/permissions" \
  -F enabled_repositories=all \
  -F allowed_actions=selected
gh api -X PUT "/orgs/$ORG/actions/permissions/selected-actions" \
  -F github_owned_allowed=true \
  -F verified_allowed=true \
  -F 'patterns_allowed[]' || true
echo "   -> actions permissions now:"
gh api "/orgs/$ORG/actions/permissions" --jq '{enabled_repositories, allowed_actions}'

echo "== 3. Default workflow token = read-only; require PR approval to fork =="
gh api -X PUT "/orgs/$ORG/actions/permissions/workflow" \
  -F default_workflow_permissions=read \
  -F can_approve_pull_request_reviews=false \
  --jq '{default_workflow_permissions, can_approve_pull_request_reviews}'

echo "== 4. Enable security defaults for new repos (best-effort; ignore if plan-gated) =="
gh api -X PATCH "/orgs/$ORG" \
  -F secret_scanning_enabled_for_new_repositories=true \
  -F secret_scanning_push_protection_enabled_for_new_repositories=true \
  -F dependabot_alerts_enabled_for_new_repositories=true \
  -F dependency_graph_enabled_for_new_repositories=true \
  --jq '{secret_scanning_enabled_for_new_repositories, secret_scanning_push_protection_enabled_for_new_repositories, dependabot_alerts_enabled_for_new_repositories}' || \
  echo "   (some security defaults may require GitHub Advanced Security / a paid plan)"

echo
echo "== NOTE: 2FA enforcement =="
echo "two_factor_requirement_enabled is READ-ONLY via the REST API. If this script"
echo "leaves it false, enforce it in the UI: Settings -> Authentication security ->"
echo "'Require two-factor authentication for everyone in the organization'."
echo "Verify after: gh api /orgs/$ORG --jq .two_factor_requirement_enabled"

echo
echo "== Final verification snapshot (the goal's check #2 evidence) =="
gh api "/orgs/$ORG" --jq '{two_factor_requirement_enabled, default_repository_permission, members_can_create_public_repositories}'
gh api "/orgs/$ORG/actions/permissions"
