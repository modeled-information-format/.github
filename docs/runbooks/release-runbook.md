---
id: 51e27ded-e4fc-41e7-9084-0c05b013bf34
type: procedural
created: 2026-06-27T23:03:08-04:00
namespace: _procedural/runbooks
title: "Release Runbook"
tags:
  - runbook
---

# Release Runbook — Audit-Gated Attested Release

This runbook governs how an org repo goes from "feature-complete" to a published,
attested release. It is the required process: a release is *enjoined* (gated) on
completing every phase below. It generalizes the MIF v1.0.0 release and applies to
any `modeled-information-format` repo on the attested-delivery architecture.

Mechanics it builds on (do not duplicate them here):

- Attested build/sign/verify: the `attested-delivery` skill references
  (`/.github/skills/attested-delivery/references/rollout-checklist.md`,
  `/.github/skills/attested-delivery/references/verification.md`) and the consuming repo’s
  `release.yml`.
- Architecture rationale: the consuming repo's release ADR (e.g. MIF ADR-015).

## Roles

- **Maintainer** — owns decisions and every outward-facing go (deploy, tag, publish).
- **Release driver** — executes the phases, opens PRs, and drives reviews.
  Outward-facing steps require maintainer sign-off.

## Invariants (hold across every phase)

- SHA-pin every GitHub Action; `pin-check` stays required.
- Required status checks must be green before any merge; never merge on a red
  required check. A non-required check that is red is still a broken window: fix the
  root cause or file a tracked follow-up before proceeding.
- Attestation verify is fail-closed; verify independently from a clean checkout,
  not just in-pipeline.
- Resolve every review thread (`required_conversation_resolution`). Reject a
  known false positive with a written rationale, then resolve it; do not leave it open.
- Write public comments, issues, and PR descriptions in plain, direct prose.
- Commit messages and artifacts carry no tool-attribution lines.
- Always use the full branch name (e.g. `develop/v1.0.0`), never an abbreviation.
- Branching model is **GitHub Flow**: `main` is the trunk; work happens on
  short-lived branches off `main`, merged via PR and deleted. Branches are rare and
  short-lived. There are no long-lived branches and no back-merge. A dedicated
  release/integration branch is an **exception**, used only to stage a large divergent
  release apart from `main` (as the v1.0.0 migration did); when used it is ephemeral
  and pruned at cutover.

## Phase 1 — Punch list (release audit)

Produce a complete, severity-tagged punch list of everything blocking the release.

1. Inventory the surface (e.g. every doc, schema, workflow, example).
2. Fan out parallel auditors over logical buckets; each returns structured findings
   (`file:line`, severity, dimension, evidence, suggested fix).
3. **Verify findings against ground truth before trusting them.** Auditor output is
   a draft, not a verdict. Re-check the dominant cluster against the actual schema,
   code, and a real gate replay. Delegated or automated audits conflate surfaces and
   overstate (example: a "fails validation" claim was false because the schema set
   `additionalProperties: true`; another conflated markdown-frontmatter keys with the
   JSON-LD projection). Downgrade or drop unconfirmed findings in the report, and say
   which were corrected and why.
Output: an audit report (the punch list), grouped by severity, with a suggested
fix order and any clean/by-design areas called out.

## Phase 2 — Epics and sub-issues

Convert the punch list into trackable work.

1. Group findings into **epics** sized as one reviewable PR each. Every finding maps
   to exactly one epic; by-design fixtures and clean files are excluded.
2. Create one GitHub **issue per epic**, labeled `epic` + `type/*` + `area/*` +
   `priority/*`.
3. Create each subtask as a **real GitHub sub-issue** linked to its epic
   (`POST /repos/{o}/{r}/issues/{epic}/sub_issues {sub_issue_id}`), labeled
   `subtask` + the same area/priority labels. A markdown checkbox list is NOT a
   subtask; do not substitute one. Create the `epic`/`subtask` labels if missing.
4. Maintainer **decisions** become their own sub-issues flagged `type/question`.
5. Mechanical, cross-cutting cleanups that touch every file (e.g. a style sweep) may
   run un-ticketed as a final pass; note this on the relevant epic so it is not lost.

## Phase 3 — Decisions

Surface every choice that is the maintainer's to make, before building on it.

1. Elicit answers with explicit, mutually-exclusive options and a recommendation.
2. Record each answer on its decision sub-issue AND in the release workplan issue
   (Phase 4), so the decision log is durable and discoverable.
3. Open decisions block their epic's PR from finalizing, not the audit.

## Phase 4 — Release workplan issue

Create one **release tracking epic** that is the single source of truth for the cutover.
It captures: current state (branch divergence/ancestry), the fixed decisions, the
prerequisite epics (the release is gated on them per the gating decision), the cutover
phases (Phase 6 below), verification, and rollback. Label `epic` + `area/ci` +
`priority/high`.

## Phase 5 — Execution (one PR per epic)

Work the epics under GitHub Flow.

1. One short-lived branch + one PR per epic, off `main` by default; each PR closes its
   epic's sub-issues and is deleted on merge. Exception: when the release is staged on
   a dedicated integration branch (a large/divergent release), target that branch
   instead; it is cut over and pruned in Phase 6.
2. All required gates green; reviews converged. Reject known false positives with a
   rationale and resolve the thread (one such finding from an automated reviewer =
   converged; do not loop it).
3. Run the final un-ticketed sweep (if any) after the epics land, to avoid conflicts.

## Phase 6 — Cutover (outward-facing; maintainer go required)

1. **Pre-merge prep** on the integration branch: apply the release-status decision
   (e.g. Release Candidate now, flip to Release at tag), confirm `VERSION.json`, and
   confirm the build emits the schema mirror and a clean `llms.txt`.
2. **Reach the release state on `main`.** Under GitHub Flow the epic PRs already
   merged to `main`, so `main` is the release state; skip to step 3. Only for the
   integration-branch exception: merge the integration branch to `main` via PR with a
   **merge commit** (never squash/rebase for the cutover) to preserve the full release
   history; the integration branch is the intended final state, so resolve conflicts
   in its favor. Required checks must pass on the PR.
3. **Deploy** is automatic on push to `main` (`deploy.yml` -> the published site).
   Verify the live site, the served schema mirror, and a clean `llms.txt`.
4. **Tag + release**: apply the status flip (promote CHANGELOG, set Release), tag the
   version, create the GitHub Release -> `release.yml` runs the attested pipeline
   (SLSA provenance + SBOM, keyless Sigstore, fail-closed verify). If the repo ships a
   Claude Code plugin, this run also pushes the plugin's dependency-resolution tag —
   see [Plugin Dependency Tags](../reference/plugin-dependency-tags.md).
5. **Verify independently** from a clean checkout:

   ```sh
   gh attestation verify <artifact> --repo <o>/<r> \
     --signer-workflow <o>/<r>/.github/workflows/release.yml
   ```
6. **Prune branches**: GitHub Flow branches are already deleted on merge. For the
   integration-branch exception, delete the integration branch once the release is
   published and verified. There is no back-merge; `main` is the trunk.

## Rollback

- Site: revert the cutover merge on `main` (re-deploys the prior state).
- Release: fail-closed verify blocks a bad artifact from publishing; if a tag is
  wrong, delete the tag/release and re-cut.

## Artifacts the process must leave behind (the audit trail)

The audit report; one issue per epic with real sub-issues; a decision log on the
decision sub-issues and the workplan issue; the release workplan issue; one PR per
epic; the cutover PR; the tag, Release, and verified attestation.
