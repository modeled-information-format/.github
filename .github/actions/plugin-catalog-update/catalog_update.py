#!/usr/bin/env python3
"""Attested catalog-updater engine.

Two modes, one shared verification rule:

  update  (hub)        For each EXTERNAL plugin entry in a marketplace.json:
                       resolve the source repo's LATEST RELEASE, dereference its
                       tag to a commit sha, verify that release's attestations
                       fail-closed, and — only if every required predicate
                       verifies — re-pin source.sha/source.ref and open a
                       zero-touch auto-merge PR whose body carries the full
                       attestation evidence.

  verify  (admission)  For each EXTERNAL entry AT ITS CURRENTLY PINNED ref/sha,
                       verify the same required predicate set fail-closed. Any
                       failure exits non-zero. This is the rule catalog-admission
                       shares so "what must verify for an external entry" lives
                       in exactly one place.

Releases only — never branch HEAD. A bump points at an attested release or it
does not happen. stdlib only; shells out to `gh` (auth via GH_TOKEN).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

# Source kinds that are EXTERNAL (object source pinned by sha); local "./path"
# string sources are never touched.
EXTERNAL_KINDS = {"github", "url", "git-subdir"}

# Default required predicate set (v1). Each item is "<predicate-uri>" optionally
# followed by whitespace + "<signer-workflow>". With no signer, verification
# constrains by --repo (SLSA build provenance, signed by the plugin repo's own
# build workflow). Seam-signed gate verdicts (sast/sca/...) are added here later
# with their signer-workflow; the verify loop already handles the signer column.
DEFAULT_PREDICATES = "https://slsa.dev/provenance/v1"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


# --------------------------------------------------------------------------- #
# gh / shell helpers
# --------------------------------------------------------------------------- #
def gh(*args: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    """Run `gh` and return the completed process."""
    return subprocess.run(
        ["gh", *args],
        check=check,
        capture_output=capture,
        text=True,
    )


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], check=check, capture_output=True, text=True)


def log_warning(msg: str) -> None:
    print(f"::warning::{msg}")


def log_notice(msg: str) -> None:
    print(f"::notice::{msg}")


# --------------------------------------------------------------------------- #
# marketplace parsing + the PURE, testable re-pin
# --------------------------------------------------------------------------- #
def external_entries(marketplace: dict) -> list[tuple[int, dict]]:
    """Return (index, entry) for every external (object-source, sha-pinned) plugin."""
    out = []
    for i, plugin in enumerate(marketplace.get("plugins", [])):
        src = plugin.get("source")
        if isinstance(src, dict) and src.get("source") in EXTERNAL_KINDS:
            out.append((i, plugin))
    return out


def source_repo(src: dict) -> str:
    """owner/repo for an external source — from `repo`, else parsed from `url`.

    claude marketplace `git-subdir`/`url` sources carry a git `url` (not a
    `repo`); `github` sources carry `repo`. Accept both.
    """
    r = src.get("repo")
    if r:
        return r.strip().strip("/")
    # Normalize first (trim whitespace + trailing slashes), THEN drop a .git
    # suffix — otherwise a `.../r.git/` form would leave `r.git`.
    url = src.get("url", "").strip().rstrip("/")
    url = url.removeprefix("https://github.com/").removeprefix("git@github.com:")
    return url.removesuffix(".git").strip("/")


def _entry_span(raw: str, plugin_name: str) -> tuple[int, int] | None:
    """Text span [start, end) of the plugins-array element whose OWN top-level
    `name` == plugin_name.

    Brace-matched (string-aware) and confirmed by parsing the element as JSON, so
    a NESTED key that happens to equal plugin_name — e.g. another entry's
    `author.name` — can never mis-match the entry. Returns None if not found.
    """
    anchor = re.search(r'"plugins"\s*:\s*\[', raw)
    i = anchor.end() if anchor is not None else 0
    n = len(raw)
    while i < n:
        while i < n and raw[i] not in "{]":
            i += 1
        if i >= n or raw[i] == "]":
            return None
        start, depth, in_str, esc = i, 0, False, False
        j = i
        while j < n:
            c = raw[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    block = raw[start:j + 1]
                    try:
                        if json.loads(block).get("name") == plugin_name:
                            return start, j + 1
                    except json.JSONDecodeError:
                        pass
                    i = j + 1
                    break
            j += 1
        else:
            return None
    return None


def repin_text(raw: str, plugin_name: str, old_sha: str, new_sha: str, new_ref: str) -> str:
    """Re-pin a single external entry in the RAW marketplace.json text.

    Scoped to the named entry, NOT the whole file: several plugins may legitimately
    pin the same commit sha (e.g. multiple `git-subdir` plugins from one repo), so
    a global sha replace would be wrong. We locate the entry via `_entry_span`
    (brace-matched, JSON-confirmed top-level `name`), then rewrite the sha and ref
    inside that span only — inserting a `ref` line before the sha when none exists.
    Formatting, key order, and inline arrays elsewhere are preserved byte-for-byte.
    Pure function — no IO — so it is unit-testable on a fixture.
    """
    if not SHA_RE.match(new_sha):
        raise ValueError(f"new_sha is not a 40-char sha: {new_sha!r}")

    # Scope to the plugins-array element whose OWN top-level name == plugin_name
    # (brace-matched + JSON-confirmed), so a nested `author.name` equal to the
    # plugin name can't mis-segment the rewrite onto the wrong entry.
    span = _entry_span(raw, plugin_name)
    if span is None:
        raise ValueError(f"plugin {plugin_name!r} not found in marketplace")
    seg_start, seg_end = span
    segment = raw[seg_start:seg_end]

    if not re.search(r'"sha"\s*:\s*"' + re.escape(old_sha) + r'"', segment):
        raise ValueError(f"sha {old_sha!r} not found in entry {plugin_name!r}")

    # Rewrite the sha value (only this entry's sha key).
    segment = re.sub(
        r'("sha"\s*:\s*")' + re.escape(old_sha) + r'(")',
        lambda m: m.group(1) + new_sha + m.group(2), segment, count=1,
    )
    # Rewrite the ref label if present; otherwise insert one before the sha line.
    if re.search(r'"ref"\s*:\s*"', segment):
        segment = re.sub(
            r'("ref"\s*:\s*")[^"]*(")',
            lambda m: m.group(1) + new_ref + m.group(2), segment, count=1,
        )
    else:
        line_m = re.search(r'(?m)^([ \t]*)"sha"\s*:', segment)
        if line_m:  # canonical multi-line layout — insert a matching-indent line
            indent, pos = line_m.group(1), line_m.start()
            segment = segment[:pos] + f'{indent}"ref": "{new_ref}",\n' + segment[pos:]
        else:  # inline source object — insert before the sha key
            inline = re.search(r'"sha"\s*:', segment)
            if inline is None:  # unreachable: sha presence validated above
                raise ValueError(f"sha key vanished for {plugin_name!r}")
            pos = inline.start()
            segment = segment[:pos] + f'"ref": "{new_ref}", ' + segment[pos:]

    return raw[:seg_start] + segment + raw[seg_end:]


# --------------------------------------------------------------------------- #
# release resolution (fetch-by-release)
# --------------------------------------------------------------------------- #
def latest_release(repo: str) -> dict | None:
    """Latest published release of `repo`, or None if it has none."""
    proc = gh("api", f"repos/{repo}/releases/latest", check=False)
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def tag_to_commit_sha(repo: str, tag: str) -> str | None:
    """Dereference a tag to its COMMIT sha (handles annotated tags)."""
    proc = gh("api", f"repos/{repo}/commits/{tag}", "--jq", ".sha", check=False)
    sha = proc.stdout.strip()
    return sha if SHA_RE.match(sha) else None


def release_tag_for_sha(repo: str, sha: str) -> str | None:
    """Find a published release whose tag points at `sha`.

    Used by verify mode when an entry pins a `sha` but omits the `ref` label:
    attestations live in a *release* keyed by tag, so we must recover the tag —
    handing a bare commit sha to `gh release download` would fail and fail-close
    a validly-pinned entry.
    """
    proc = gh("api", "--paginate", f"repos/{repo}/releases", "--jq", ".[].tag_name", check=False)
    for tag in proc.stdout.split():
        if tag_to_commit_sha(repo, tag) == sha:
            return tag
    return None


def download_release_assets(repo: str, tag: str, dest: str) -> list[str]:
    """Download all assets of a release; return local file paths."""
    proc = gh("release", "download", tag, "--repo", repo, "--dir", dest, check=False)
    if proc.returncode != 0:
        return []
    return [os.path.join(dest, f) for f in sorted(os.listdir(dest))]


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# verification — the shared, fail-closed rule
# --------------------------------------------------------------------------- #
def parse_predicates(spec: str) -> list[tuple[str, str | None]]:
    """Parse the predicate spec into (predicate-uri, signer-workflow|None) rows.

    Fail closed: an empty spec is an error (verifying against no predicate would
    let a bump through unproven).
    """
    rows: list[tuple[str, str | None]] = []
    for line in spec.replace(",", "\n").splitlines():
        parts = line.split()
        if not parts:
            continue
        rows.append((parts[0], parts[1] if len(parts) > 1 else None))
    if not rows:
        raise ValueError("predicate spec is empty (fail closed): name at least one predicate URI")
    return rows


def _summarize_verify(stdout: str) -> str:
    """Distil `gh attestation verify --format json` into a compact, readable
    evidence block (predicate, signer identity, issuer) for the PR body. Falls
    back to the raw text if it is not the expected JSON."""
    try:
        recs = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return stdout.strip()
    if not isinstance(recs, list):
        return stdout.strip()

    def _d(v: object) -> dict:
        return v if isinstance(v, dict) else {}

    blocks = []
    for r in recs:
        vr = _d(_d(r).get("verificationResult"))
        cert = _d(_d(vr.get("signature")).get("certificate"))
        stmt = _d(vr.get("statement"))
        predicate = stmt.get("predicateType")
        signer = cert.get("buildSignerURI") or cert.get("subjectAlternativeName")
        issuer = cert.get("issuer")
        if not (predicate or signer or issuer):
            continue  # non-dict / junk record with nothing usable — skip it
        blocks.append(
            f"predicate: {predicate or '?'}\n"
            f"signer:    {signer or '?'}\n"
            f"issuer:    {issuer or '?'}"
        )
    # Empty/unexpected shape -> fall back to raw so the evidence block is never blank.
    return "\n\n".join(blocks) if blocks else stdout.strip()


def verify_subject(subject: str, repo: str, predicates: list[tuple[str, str | None]]) -> list[dict]:
    """Verify one subject (file path or oci ref) against each required predicate.

    Returns one record per predicate: {predicate, signer, ok, output}. Mirrors
    reusable-verify-gates.yml: one signer per check, --signer-workflow when the
    predicate is seam-signed, else --repo for repo-signed provenance.
    """
    results = []
    for predicate, signer in predicates:
        cmd = ["attestation", "verify", subject, "--repo", repo,
               "--predicate-type", predicate, "--format", "json"]
        if signer:
            cmd += ["--signer-workflow", signer]
        proc = gh(*cmd, check=False)
        ok = proc.returncode == 0
        # gh attestation verify suppresses its human-readable summary when stdout
        # is not a TTY (headless CI), leaving stdout+stderr empty on success — so
        # capture --format json and distil it; on failure stderr carries the error.
        output = _summarize_verify(proc.stdout) if ok else (proc.stdout + proc.stderr).strip()
        results.append(
            {
                "predicate": predicate,
                "signer": signer or f"repo:{repo}",
                "ok": ok,
                "output": output,
            }
        )
    return results


def verify_release(repo: str, tag: str, predicates: list[tuple[str, str | None]]) -> dict:
    """Download a release's subjects and verify them. PASS iff some asset verifies
    EVERY required predicate. Returns the evidence record used to gate + render.
    """
    with tempfile.TemporaryDirectory() as tmp:
        assets = download_release_assets(repo, tag, tmp)
        if not assets:
            return {"ok": False, "reason": "no release assets to verify", "subject": None, "checks": []}
        checks: list[dict] = []
        for asset in assets:
            checks = verify_subject(asset, repo, predicates)
            if all(c["ok"] for c in checks):
                return {
                    "ok": True,
                    "subject": os.path.basename(asset),
                    "digest": "sha256:" + sha256_file(asset),
                    "checks": checks,
                }
        # None fully verified — report the last asset's checks as the evidence.
        return {
            "ok": False,
            "reason": "no asset verified every required predicate",
            "subject": os.path.basename(assets[-1]),
            "digest": "sha256:" + sha256_file(assets[-1]),
            "checks": checks,
        }


# --------------------------------------------------------------------------- #
# PR body
# --------------------------------------------------------------------------- #
def render_pr_body(plugin_name: str, repo: str, old_ref: str, new_ref: str,
                   old_sha: str, new_sha: str, release: dict, evidence: dict) -> str:
    rows = "\n".join(
        f"| `{c['predicate']}` | `{c['signer']}` | `{repo}` | {'✅ verified' if c['ok'] else '❌ FAILED'} |"
        for c in evidence["checks"]
    )
    raw = "\n\n".join(
        f"### `{c['predicate']}`\n```\n{c['output']}\n```" for c in evidence["checks"]
    )
    subject = evidence.get("subject") or "(n/a)"
    digest = evidence.get("digest") or "(n/a)"
    # One re-verify command per predicate, carrying --signer-workflow for
    # seam-signed predicates so a reviewer reproduces exactly what was verified
    # (--repo alone is insufficient for seam-signed gates; org CLAUDE.md §5).
    # --format json mirrors how the engine verifies, so the command produces
    # evidence even in a non-TTY context (plain output is suppressed headless).
    if evidence["checks"]:
        reverify = "\n".join(
            f"gh attestation verify {subject} --repo {repo} --predicate-type {c['predicate']} --format json"
            + ("" if c["signer"].startswith("repo:") else f" \\\n  --signer-workflow {c['signer']}")
            for c in evidence["checks"]
        )
    else:
        reverify = f"gh attestation verify {subject} --repo {repo} --predicate-type <predicate> --format json"
    return f"""\
Automated, **verify-first** re-pin of an external plugin to its latest attested release.

## Bump
- **Plugin:** `{plugin_name}` — source repo `{repo}`
- **ref:** `{old_ref}` → `{new_ref}`
- **sha:** `{old_sha[:12]}` → `{new_sha}`
- **Release:** {release.get('html_url', '(n/a)')} (published {release.get('published_at', '(n/a)')})

## Verified subject
- **Artifact:** `{subject}`
- **Digest:** `{digest}`

## Attestations
| Predicate | Signer | Source repo | Verdict |
| --- | --- | --- | --- |
{rows}

Only a release whose **every** required predicate verifies reaches this PR, so the
table above is all-green by construction.

<details><summary>Raw <code>gh attestation verify</code> evidence</summary>

{raw}
</details>

## Re-verify it yourself
```bash
{reverify}
```

`catalog-admission` re-runs this verification **fail-closed** on this PR; the PR
**auto-merges** once admission + the required gates are green.
"""


# --------------------------------------------------------------------------- #
# modes
# --------------------------------------------------------------------------- #
def default_branch(repo: str) -> str:
    proc = gh("api", f"repos/{repo}", "--jq", ".default_branch", check=False)
    return proc.stdout.strip() or "main"


def branch_slug(plugin_name: str) -> str:
    """A git-ref-safe slug for a plugin name (for the PR branch).

    Plugin names may contain characters git rejects in a ref component. Map any
    non-[A-Za-z0-9._-] run to '-', collapse dot runs (kills '..'), strip leading/
    trailing '.'/'-', drop a trailing '.lock', and fall back to 'plugin'. Keeps
    the real name for the PR title/commit.
    """
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", plugin_name)
    slug = re.sub(r"\.{2,}", ".", slug).strip(".-")
    if slug.endswith(".lock"):
        slug = slug[: -len(".lock")].strip(".-")
    return slug or "plugin"


def open_pr(repo: str, plugin_name: str, new_text: str, marketplace_path: str,
            new_ref: str, body: str) -> None:
    """Branch, commit the single-entry re-pin, push, open PR, enable auto-merge."""
    branch = f"deps/external-plugin/{branch_slug(plugin_name)}"
    base = default_branch(repo)
    git("switch", "-C", branch, f"origin/{base}")
    with open(marketplace_path, "w", encoding="utf-8") as fh:
        fh.write(new_text)
    git("add", marketplace_path)
    git("commit", "-m", f"chore(catalog): re-pin {plugin_name} to {new_ref}")
    # The branch namespace is bot-exclusive and the content is deterministic, so a
    # plain --force is correct. --force-with-lease would refuse on a re-run: the
    # fresh checkout has no remote-tracking ref for an already-pushed bot branch.
    git("push", "--force", "-u", "origin", branch)
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as bf:
        bf.write(body)
        body_file = bf.name
    try:
        title = f"chore(catalog): re-pin {plugin_name} to {new_ref}"
        # gh pr edit/merge want a PR number/URL — a branch name is not a reliable
        # selector — so resolve the number for this head branch and pass it.
        def pr_number() -> str:
            return gh("pr", "list", "--repo", repo, "--head", branch, "--json", "number",
                      "--jq", ".[0].number // empty", check=False).stdout.strip()

        num = pr_number()
        if num:
            gh("pr", "edit", num, "--repo", repo, "--title", title, "--body-file", body_file, check=False)
        else:
            gh("pr", "create", "--repo", repo, "--head", branch, "--base", base,
               "--title", title, "--body-file", body_file, check=False)
            num = pr_number()
        if num:
            gh("pr", "merge", num, "--repo", repo, "--auto", "--squash", check=False)
        else:
            log_warning(f"{plugin_name}: could not resolve a PR number on {branch} — auto-merge not enabled")
    finally:
        os.unlink(body_file)
    log_notice(f"opened/updated auto-merge PR for {plugin_name} on {branch}")


def mode_update(repo: str, marketplace_path: str, predicates: list[tuple[str, str | None]],
                dry_run: bool) -> int:
    with open(marketplace_path, encoding="utf-8") as fh:
        raw = fh.read()
    mp = json.loads(raw)
    entries = external_entries(mp)
    if not entries:
        log_notice(f"{repo}: no external plugin entries — nothing to update")
        return 0

    for _, plugin in entries:
        name = plugin.get("name", "?")
        # One bad entry (a flaky gh call, a malformed source) must not abort the
        # whole repo's run — isolate each entry, warn, and carry on.
        try:
            src = plugin["source"]
            src_repo = source_repo(src)
            old_sha = str(src.get("sha", ""))
            old_ref = str(src.get("ref", ""))

            release = latest_release(src_repo)
            if not release:
                log_notice(f"{name}: {src_repo} has no published release — skipping")
                continue
            tag = release.get("tag_name", "")
            new_sha = tag_to_commit_sha(src_repo, tag)
            if not new_sha:
                log_warning(f"{name}: could not resolve {src_repo}@{tag} to a commit sha — skipping")
                continue
            if new_sha == old_sha:
                log_notice(f"{name}: already at latest release {tag} ({new_sha[:12]}) — no change")
                continue

            evidence = verify_release(src_repo, tag, predicates)
            if not evidence["ok"]:
                log_warning(
                    f"{name}: release {tag} did NOT verify ({evidence.get('reason', 'failed')}) "
                    f"— NOT re-pinning (fail-closed)"
                )
                continue

            new_text = repin_text(raw, name, old_sha, new_sha, tag)
            body = render_pr_body(name, src_repo, old_ref, tag, old_sha, new_sha, release, evidence)
            print(f"=== {name}: {old_ref} ({old_sha[:12]}) -> {tag} ({new_sha[:12]}) — VERIFIED ===")
            if dry_run:
                print(body)
                log_notice(f"[dry-run] would open auto-merge PR for {name}")
                continue
            open_pr(repo, name, new_text, marketplace_path, tag, body)
        except Exception as exc:  # noqa: BLE001 - isolate per-entry failures
            log_warning(f"{name}: update failed ({exc}) — skipping this entry")
    return 0


def mode_verify(marketplace_path: str, predicates: list[tuple[str, str | None]]) -> int:
    """Fail-closed verification of every external entry at its pinned ref."""
    with open(marketplace_path, encoding="utf-8") as fh:
        mp = json.load(fh)
    entries = external_entries(mp)
    if not entries:
        log_notice("no external plugin entries to verify")
        return 0
    failed = 0
    for _, plugin in entries:
        name = plugin.get("name", "?")
        src = plugin["source"]
        src_repo = source_repo(src)
        # Verify the release artifact, which is keyed by TAG. Prefer the entry's
        # ref label; if it omits one, recover the tag from the pinned sha rather
        # than handing a bare commit sha to `gh release download`.
        sha = str(src.get("sha", ""))
        tag = str(src.get("ref", "")) or (release_tag_for_sha(src_repo, sha) if sha else "")
        if not tag:
            print(f"::error::{name}: no release tag found for {src_repo}@{sha or '(unpinned)'} "
                  f"— cannot verify (fail closed)")
            failed = 1
            continue
        evidence = verify_release(src_repo, tag, predicates)
        if evidence["ok"]:
            log_notice(f"{name}: {src_repo}@{tag} attestations verified")
        else:
            print(f"::error::{name}: {src_repo}@{tag} failed verification "
                  f"({evidence.get('reason', 'failed')})")
            failed = 1
    return failed


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Attested catalog-updater engine")
    ap.add_argument("--mode", choices=["update", "verify"], required=True)
    ap.add_argument("--repo", required=True, help="owner/repo of the marketplace being processed")
    ap.add_argument("--marketplace", default=".claude-plugin/marketplace.json")
    ap.add_argument("--predicates", default=DEFAULT_PREDICATES)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    try:
        predicates = parse_predicates(args.predicates)
    except ValueError as exc:
        print(f"::error::{exc}")
        return 1
    if args.mode == "update":
        return mode_update(args.repo, args.marketplace, predicates, args.dry_run)
    return mode_verify(args.marketplace, predicates)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
