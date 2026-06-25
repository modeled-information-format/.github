# attested-delivery — Claude Code plugin

Onboard a repository or organization to the **attested release architecture**:
releases that are signed, SLSA-attested, and refused at the door unless every
required attestation re-verifies.

This plugin packages the org's own machinery for AI agents:

- **Skill** — `skills/attested-delivery/` — the architect & onboarding skill
  (phase protocol, the central-reusables catalog, integration recipes, the
  independent verification command set, and the hard-won platform-constraint traps).
- **Agent** — `agents/attested-delivery.md` — an attested-delivery specialist,
  authored once and valid as **both** a Claude subagent and a GitHub Copilot custom
  agent (it lives in Copilot's `.github/agents/` path and is discovered by Claude
  through this plugin's manifest).
- **Bundled workflow resources** — `workflows/` — the 19 central reusable workflows
  themselves. The skill points at them by name as the single source of truth (no
  copies), referencing each at `${CLAUDE_PLUGIN_ROOT}/workflows/<name>.yml`. They are
  enumerated deliberately in `skills/attested-delivery/references/workflow-catalog.md`.

## Why the plugin root is `.github/`

The manifest is `.github/.claude-plugin/plugin.json`, so the **`.github/` directory
is the plugin root**. This is deliberate:

- The agent falls out of the **default** `agents/` scan at `.github/agents/` — which
  is exactly GitHub Copilot's custom-agent path. One file, both platforms, no custom
  manifest paths.
- The skill falls out of the **default** `skills/` scan at `.github/skills/`,
  alongside the org's other skills.
- The 19 reusable workflows at `.github/workflows/` are bundled plugin resources
  under the root, reachable via `${CLAUDE_PLUGIN_ROOT}/workflows/`.

(A manifest nested deeper could not reference `.github/agents/` — plugin component
paths forbid `../`. Rooting at `.github/` is what makes the single dual-platform
agent work.)

## Install

```bash
# from a local checkout of this repo; the plugin root is the `.github/`
# directory inside the checkout (replace <repo> with your clone path)
claude --plugin-dir <repo>/.github

# or validate the plugin structure
claude plugin validate <repo>/.github
```

Once enabled, the `attested-delivery` skill triggers on phrases like "onboard to
attested delivery", "set up release signing", "wire the attestation seam", or
"verify release attestations"; the `attested-delivery` agent is dispatchable for
the same domain.

## Composition

The `attested-delivery` skill owns the **release backbone** (SLSA L3 container
signing, the attestation seam, fail-closed verify, `pin-check`). For end-to-end
**quality-gate coverage assessment** across the 12-gate map, compose with the
companion `gh-attested` skill (installed separately, not bundled in this plugin) —
it defers build-provenance and SBOM attestation to this one.

See the [docs site](https://modeled-information-format.github.io/docs/) for the full
concepts, ADRs, and promotion-pipeline specifications.
