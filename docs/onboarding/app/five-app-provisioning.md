# Five-App Fleet — Reference

The org's automation authenticates as **five least-privilege GitHub Apps**. Each
mints short-lived installation tokens via SHA-pinned
`actions/create-github-app-token` using its OAuth **client-id** (the deprecated
numeric `app-id` is retired as an auth input). Governed by
[ADR-011](../../adr/ADR-011-least-privilege-app-fleet.md); the machine-readable
source of truth is [`auth/apps.json`](../../../auth/apps.json).

## The fleet

Every app's client-id lives in an org **variable** and its private key in an org
**secret**, both at visibility **All**.

| Role | App name | Client ID | App ID | Variable (client-id) | Secret (private key) |
| --- | --- | --- | --- | --- | --- |
| `ci` | MIF CI | `Iv23liwIhF5oJTKzV2LP` | `4186958` | `CI_CLIENT_APP_ID` | `CI_CLIENT_APP_PRIVATE_KEY` |
| `catalog` | MIF Catalog | `Iv23liSw92oSTGWAOCGO` | `4187002` | `CATALOG_CLIENT_APP_ID` | `CATALOG_CLIENT_APP_PRIVATE_KEY` |
| `pages` | MIF Pages | `Iv23liT9K2pQNdziydw4` | `4187014` | `PAGES_CLIENT_APP_ID` | `PAGES_CLIENT_APP_PRIVATE_KEY` |
| `automerge` | MIF Automerge | `Iv23li1wVKsTbJ0tVv2d` | `4187029` | `AUTOMERGE_CLIENT_APP_ID` | `AUTOMERGE_CLIENT_APP_PRIVATE_KEY` |
| `release` | MIF Release | `Iv23lii4nELn3fIt6FsT` | | `RELEASE_CLIENT_APP_ID` | `RELEASE_CLIENT_APP_PRIVATE_KEY` |

## Common configuration

Identical across all five apps:

| Setting | Value |
| --- | --- |
| Homepage URL | `https://mif-spec.dev` |
| Callback URL | blank |
| Setup URL | blank |
| Webhook | inactive — a token-minting identity, not webhook-driven |
| Organization permissions | none (all No access) |
| Account permissions | none (all No access) |
| Event subscriptions | none |
| Installation | only `modeled-information-format`, all repositories |
| `Metadata` | Read-only (set automatically by GitHub) |

Every repository permission not listed for an app below is **No access**.

## Repository permissions

### `ci` — CI / OpenSSF Scorecard identity

Read-only cross-repo CI, primarily OpenSSF Scorecard reading branch protection.
`Administration: Read-only` is what lets Scorecard score Branch-Protection from the
real settings.

| Permission | Level |
| --- | --- |
| Administration | Read-only |
| Checks | Read-only |
| Contents | Read-only |
| Issues | Read-only |
| Pull requests | Read-only |
| Actions | Read-only |

### `catalog` — marketplace catalog updates

Re-pins external plugin entries in the Claude Code plugin marketplace catalog to
their latest attested release and opens auto-merge PRs.

| Permission | Level |
| --- | --- |
| Contents | Read and write |
| Pull requests | Read and write |
| Actions | Read and write |

### `pages` — cross-repo org Pages deploy

Cross-repo GitHub Pages deploy/notify: docs-source repos build, then notify the
`github.io` assembly repo to compose and deploy.

| Permission | Level |
| --- | --- |
| Contents | Read and write |
| Pages | Read and write |
| Actions | Read and write |

### `automerge` — Dependabot auto-merge

Approves and enables auto-merge on Dependabot PRs (Dependabot cannot approve its
own PR).

| Permission | Level |
| --- | --- |
| Contents | Read and write |
| Pull requests | Read and write |

### `release` — release publish / contents

Authenticates the `gh release` / contents-write steps in release workflows. Keyless
OIDC attestation is unchanged and does not use this app.

| Permission | Level |
| --- | --- |
| Contents | Read and write |
| Packages | Read and write (only where the repo publishes packages) |

## Icon colors

One accent per role on the MIF dark field (`ci` and `automerge` reuse the brand
accents); distinct in hue and lightness so a one-letter glyph reads on a dark
avatar and the set stays colorblind-distinguishable.

| App | Hex | Rationale |
| --- | --- | --- |
| `ci` | `#34D3E8` | machine-cyan, a read-only machine identity |
| `catalog` | `#A371F7` | violet, marketplace / catalog |
| `pages` | `#3FB950` | green, deploy / live site |
| `automerge` | `#F5B642` | human-amber, the approval Dependabot cannot give |
| `release` | `#F2557D` | rose-red, ship / cut a release |

## Credential provisioning

`gh secret/variable set --org` does not work for this org; credentials are set via
the REST API with an org-admin token. The **variable** holds the client-id
(`Iv23...`, not the numeric app id); the **secret** holds the private key,
libsodium-sealed against the org public key.

```bash
TOK=<org-admin token>

# Variable (client-id), visibility all:
curl -sS -X POST -H "Authorization: Bearer $TOK" -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/orgs/modeled-information-format/actions/variables \
  -d '{"name":"CI_CLIENT_APP_ID","value":"Iv23xxxxxxxxxxxx","visibility":"all"}'

# Secret (private key): GET the org public key, sealed-box encrypt the PEM against
# it, then PUT { encrypted_value, key_id, visibility: "all" } to
# /orgs/modeled-information-format/actions/secrets/CI_CLIENT_APP_PRIVATE_KEY
```

The same pair is set for every `<ROLE>_CLIENT_APP_ID` / `<ROLE>_CLIENT_APP_PRIVATE_KEY`.

## Related

- [ADR-011](../../adr/ADR-011-least-privilege-app-fleet.md) — the decision record.
- [`auth/apps.json`](../../../auth/apps.json) — the machine-readable source of truth.
- `.github/workflows/app-manifest-validate.yml` — the gate that keeps `auth/apps.json`
  consistent (SHA pin, role/name match, uniqueness, permission enums, consumer paths).
