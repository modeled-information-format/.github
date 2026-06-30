# Five-App Fleet — Provisioning Guide

How to create and provision the five least-privilege GitHub Apps that org
workflows authenticate as. Governed by [ADR-011](../../adr/ADR-011-least-privilege-app-fleet.md);
the machine-readable source of truth is [`auth/apps.json`](../../../auth/apps.json).

Each app mints short-lived installation tokens via SHA-pinned
`actions/create-github-app-token` using its OAuth **client-id** (the deprecated
`app-id` is retired). Per app: the client-id lives in an org **variable**
`<ROLE>_CLIENT_APP_ID`; the private key in an org **secret**
`<ROLE>_CLIENT_APP_PRIVATE_KEY`; both at visibility **All**.

> Every value below is in its own code block — use the copy button. Repository
> permissions are toggles in the form, not pasteable strings, so they stay as a list.

## Common settings (identical for all five)

Set these on every app in the **Register new GitHub App** form
(`https://github.com/organizations/modeled-information-format/settings/apps/new`):

**Homepage URL** (same for all five):

```text
https://mif-spec.dev
```

- Callback URL — *leave blank*
- Setup URL — *leave blank*
- Webhook -> Active — **Unchecked** (token-minting identity, not webhook-driven)
- Webhook URL — *blank (allowed once Active is off)*
- Organization permissions — None (all "No access")
- Account permissions — None (all "No access")
- Subscribe to events — None
- Where can this app be installed? — **Only on this account** (`modeled-information-format`)

Every repository permission not listed for an app stays **No access**.
`Metadata: Read-only` is set automatically by GitHub.

After creating each app:

1. **Generate a private key** (`.pem`) and store it in the app's org secret.
2. **Copy the Client ID** (`Iv23...`) and store it in the app's org variable.
3. **Install** the app on **All repositories** in the org.

---

## 1. `ci` — CI / OpenSSF Scorecard identity

App name:

```text
MIF CI
```

Description:

```text
Org CI identity for the modeled-information-format org. Mints short-lived installation tokens for read-only cross-repo CI — primarily OpenSSF Scorecard reading branch protection. Least-privilege; governed by ADR-011.
```

Repository permissions (set in the form):

- Administration: Read-only
- Checks: Read-only
- Contents: Read-only
- Issues: Read-only
- Pull requests: Read-only
- Actions: Read-only

`Administration: Read-only` is what lets Scorecard score Branch-Protection from real settings.

Org variable (store the Client ID here):

```text
CI_CLIENT_APP_ID
```

Org secret (store the private key here):

```text
CI_CLIENT_APP_PRIVATE_KEY
```

---

## 2. `catalog` — marketplace catalog updates

App name:

```text
MIF Catalog
```

Description:

```text
Updates the modeled-information-format Claude Code plugin marketplace catalog — re-pins external plugin entries to their latest attested release and opens auto-merge PRs. Least-privilege; governed by ADR-011.
```

Repository permissions (set in the form):

- Contents: Read and write
- Pull requests: Read and write
- Actions: Read and write

Org variable:

```text
CATALOG_CLIENT_APP_ID
```

Org secret:

```text
CATALOG_CLIENT_APP_PRIVATE_KEY
```

---

## 3. `pages` — cross-repo org Pages deploy

App name:

```text
MIF Pages
```

Description:

```text
Cross-repo GitHub Pages deploy/notify for the modeled-information-format org — docs-source repos build, then notify the github.io assembly repo to compose and deploy. Least-privilege; governed by ADR-011.
```

Repository permissions (set in the form):

- Contents: Read and write
- Pages: Read and write
- Actions: Read and write

Org variable:

```text
PAGES_CLIENT_APP_ID
```

Org secret:

```text
PAGES_CLIENT_APP_PRIVATE_KEY
```

---

## 4. `automerge` — Dependabot auto-merge

App name:

```text
MIF Automerge
```

Description:

```text
Approves and enables auto-merge on Dependabot PRs across the modeled-information-format org (Dependabot cannot approve its own PR). Least-privilege; governed by ADR-011.
```

Repository permissions (set in the form):

- Contents: Read and write
- Pull requests: Read and write

Org variable:

```text
AUTOMERGE_CLIENT_APP_ID
```

Org secret:

```text
AUTOMERGE_CLIENT_APP_PRIVATE_KEY
```

---

## 5. `release` — release publish / contents

App name:

```text
MIF Release
```

Description:

```text
Authenticates the gh release / contents-write steps in release workflows across the modeled-information-format org. Keyless OIDC attestation is unchanged. Least-privilege; governed by ADR-011.
```

Repository permissions (set in the form):

- Contents: Read and write
- Packages: Read and write (only where the repo publishes packages)

Org variable:

```text
RELEASE_CLIENT_APP_ID
```

Org secret:

```text
RELEASE_CLIENT_APP_PRIVATE_KEY
```

---

## Credential name summary

| App | Variable (Client ID) | Secret (Private key) |
| --- | --- | --- |
| `ci` | `CI_CLIENT_APP_ID` | `CI_CLIENT_APP_PRIVATE_KEY` |
| `catalog` | `CATALOG_CLIENT_APP_ID` | `CATALOG_CLIENT_APP_PRIVATE_KEY` |
| `pages` | `PAGES_CLIENT_APP_ID` | `PAGES_CLIENT_APP_PRIVATE_KEY` |
| `automerge` | `AUTOMERGE_CLIENT_APP_ID` | `AUTOMERGE_CLIENT_APP_PRIVATE_KEY` |
| `release` | `RELEASE_CLIENT_APP_ID` | `RELEASE_CLIENT_APP_PRIVATE_KEY` |

## Provisioning the org variable + secret

`gh secret/variable set --org` does not work for this org from the CLI; use the
REST API with the org-admin token. The **variable** holds the Client ID
(`Iv23...` — not the numeric app id); the **secret** holds the private key,
libsodium-sealed against the org public key.

```bash
TOK=<org-admin token>

# 1. Variable (Client ID), visibility all
curl -sS -X POST -H "Authorization: Bearer $TOK" -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/orgs/modeled-information-format/actions/variables \
  -d '{"name":"CI_CLIENT_APP_ID","value":"Iv23xxxxxxxxxxxx","visibility":"all"}'

# 2. Secret (private key): GET the org public key, sealed-box encrypt the PEM with
#    that key, then PUT { encrypted_value, key_id, visibility:"all" } to
#    /orgs/modeled-information-format/actions/secrets/CI_CLIENT_APP_PRIVATE_KEY
```

Repeat for all five `<ROLE>_CLIENT_APP_ID` / `<ROLE>_CLIENT_APP_PRIVATE_KEY` pairs.

## After provisioning

- The auth refactor PRs (epic `#37`) go green: each workflow mints its app token
  via `client-id`.
- Verify a release still attests and verifies (`gh attestation verify`) — the
  `release` app only authenticates the publish step; the keyless OIDC attestation
  identity is unchanged.
- The manifest gate (`.github/workflows/app-manifest-validate.yml`) keeps
  `auth/apps.json` consistent (SHA pin, role/name match, uniqueness, permission
  enums, consumer paths).
