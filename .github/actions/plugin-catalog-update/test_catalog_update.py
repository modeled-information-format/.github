#!/usr/bin/env python3
"""Unit tests for the pure (IO-free) parts of the catalog-updater engine."""

import json
import unittest

import catalog_update as cu

# A fixture catalog: one local entry (must be untouched) + one external entry.
FIXTURE = """\
{
  "name": "attested-delivery",
  "owner": { "name": "attested-delivery" },
  "plugins": [
    {
      "name": "attested-reference",
      "source": "./plugins/attested-reference",
      "keywords": ["reference", "attested", "example"]
    },
    {
      "name": "acme-widgets",
      "source": {
        "source": "git-subdir",
        "repo": "acme/widgets",
        "subdir": "plugins/widgets",
        "ref": "v1.2.3",
        "sha": "1111111111111111111111111111111111111111"
      },
      "keywords": ["widgets"]
    }
  ]
}
"""

NEW_SHA = "2222222222222222222222222222222222222222"


OLD_SHA = "1111111111111111111111111111111111111111"

# Two plugins from ONE repo at the SAME sha — a legitimate git-subdir layout that
# the old global-uniqueness re-pin mishandled.
DUP_FIXTURE = """\
{
  "name": "attested-delivery",
  "plugins": [
    {
      "name": "acme-alpha",
      "source": {
        "source": "git-subdir", "repo": "acme/suite", "subdir": "plugins/alpha",
        "ref": "v1.0.0", "sha": "1111111111111111111111111111111111111111"
      }
    },
    {
      "name": "acme-beta",
      "source": {
        "source": "git-subdir", "repo": "acme/suite", "subdir": "plugins/beta",
        "ref": "v1.0.0", "sha": "1111111111111111111111111111111111111111"
      }
    }
  ]
}
"""

# An external entry that omits the optional `ref` label.
NOREF_FIXTURE = """\
{
  "name": "attested-delivery",
  "plugins": [
    {
      "name": "acme-widgets",
      "source": {
        "source": "git-subdir",
        "repo": "acme/widgets",
        "sha": "1111111111111111111111111111111111111111"
      }
    }
  ]
}
"""


class RepinText(unittest.TestCase):
    def test_rewrites_sha_and_ref_only(self):
        out = cu.repin_text(FIXTURE, "acme-widgets", OLD_SHA, NEW_SHA, "v2.0.0")
        mp = json.loads(out)
        src = mp["plugins"][1]["source"]
        self.assertEqual(src["sha"], NEW_SHA)
        self.assertEqual(src["ref"], "v2.0.0")

    def test_local_entry_and_formatting_preserved(self):
        out = cu.repin_text(FIXTURE, "acme-widgets", OLD_SHA, NEW_SHA, "v2.0.0")
        # The local source line and the inline keywords array are byte-preserved.
        self.assertIn('"source": "./plugins/attested-reference"', out)
        self.assertIn('"keywords": ["reference", "attested", "example"]', out)
        # Only the sha and ref tokens changed; everything else identical.
        expected = FIXTURE.replace(OLD_SHA, NEW_SHA).replace('"ref": "v1.2.3"', '"ref": "v2.0.0"')
        self.assertEqual(out, expected)

    def test_shared_sha_only_targets_named_entry(self):
        # Re-pinning acme-beta must NOT touch acme-alpha, even though both pin the
        # same sha (the old global replace would have hit both / hard-failed).
        out = cu.repin_text(DUP_FIXTURE, "acme-beta", OLD_SHA, NEW_SHA, "v2.0.0")
        mp = json.loads(out)
        self.assertEqual(mp["plugins"][0]["source"]["sha"], OLD_SHA)   # alpha untouched
        self.assertEqual(mp["plugins"][0]["source"]["ref"], "v1.0.0")
        self.assertEqual(mp["plugins"][1]["source"]["sha"], NEW_SHA)   # beta re-pinned
        self.assertEqual(mp["plugins"][1]["source"]["ref"], "v2.0.0")

    def test_inserts_ref_when_absent(self):
        out = cu.repin_text(NOREF_FIXTURE, "acme-widgets", OLD_SHA, NEW_SHA, "v3.0.0")
        src = json.loads(out)["plugins"][0]["source"]
        self.assertEqual(src["sha"], NEW_SHA)
        self.assertEqual(src["ref"], "v3.0.0")  # ref inserted

    def test_rejects_bad_new_sha(self):
        with self.assertRaises(ValueError):
            cu.repin_text(FIXTURE, "acme-widgets", OLD_SHA, "nope", "v2.0.0")

    def test_rejects_missing_entry(self):
        with self.assertRaises(ValueError):
            cu.repin_text(FIXTURE, "no-such-plugin", OLD_SHA, NEW_SHA, "v2.0.0")

    def test_rejects_sha_not_in_entry(self):
        with self.assertRaises(ValueError):
            cu.repin_text(FIXTURE, "acme-widgets", "9999999999999999999999999999999999999999",
                          NEW_SHA, "v2.0.0")

    def test_plugin_named_like_marketplace(self):
        # A plugin whose name equals the marketplace `name` must re-pin its own
        # entry, not mis-segment on the marketplace-level name key.
        fixture = """\
{
  "name": "attested-delivery",
  "owner": { "name": "attested-delivery" },
  "plugins": [
    {
      "name": "attested-delivery",
      "source": {
        "source": "git-subdir", "repo": "a/b", "subdir": "p",
        "ref": "v1", "sha": "1111111111111111111111111111111111111111"
      }
    }
  ]
}
"""
        out = cu.repin_text(fixture, "attested-delivery", OLD_SHA, NEW_SHA, "v2")
        src = json.loads(out)["plugins"][0]["source"]
        self.assertEqual(src["sha"], NEW_SHA)
        self.assertEqual(src["ref"], "v2")


class BranchSlug(unittest.TestCase):
    def test_git_invalid_forms_normalized(self):
        cases = {
            "acme/widgets:beta": "acme-widgets-beta",   # slashes/colon → -
            "my plugin": "my-plugin",                   # space → -
            "..dots..": "dots",                         # collapse + strip dots
            ".hidden": "hidden",                         # leading dot
            "trailing.": "trailing",                     # trailing dot
            "weird.lock": "weird",                       # trailing .lock
            "！！！": "plugin",                           # all-invalid → fallback
        }
        for raw, want in cases.items():
            self.assertEqual(cu.branch_slug(raw), want, raw)
        # No result starts/ends with '.' or '-', has '..', or ends with '.lock'.
        for raw in cases:
            s = cu.branch_slug(raw)
            self.assertFalse(s.startswith((".", "-")) or s.endswith((".", "-")))
            self.assertNotIn("..", s)
            self.assertFalse(s.endswith(".lock"))


class ExternalEntries(unittest.TestCase):
    def test_only_object_external_sources(self):
        mp = json.loads(FIXTURE)
        entries = cu.external_entries(mp)
        self.assertEqual([i for i, _ in entries], [1])
        self.assertEqual(entries[0][1]["name"], "acme-widgets")


class ParsePredicates(unittest.TestCase):
    def test_uri_only(self):
        self.assertEqual(cu.parse_predicates("https://slsa.dev/provenance/v1"),
                         [("https://slsa.dev/provenance/v1", None)])

    def test_uri_with_signer_and_multiline(self):
        spec = "https://slsa.dev/provenance/v1\nhttps://ex/sast/v1 owner/.github/.github/workflows/x.yml"
        self.assertEqual(
            cu.parse_predicates(spec),
            [("https://slsa.dev/provenance/v1", None),
             ("https://ex/sast/v1", "owner/.github/.github/workflows/x.yml")],
        )

    def test_empty_fails_closed(self):
        with self.assertRaises(ValueError):
            cu.parse_predicates("   ")


class RenderBody(unittest.TestCase):
    def test_contains_bump_and_attestations(self):
        evidence = {
            "ok": True,
            "subject": "widgets-2.0.0.tgz",
            "digest": "sha256:abc",
            "checks": [{"predicate": "https://slsa.dev/provenance/v1",
                        "signer": "repo:acme/widgets", "ok": True, "output": "Verified"}],
        }
        body = cu.render_pr_body(
            "acme-widgets", "acme/widgets", "v1.2.3", "v2.0.0",
            "1111111111111111111111111111111111111111", NEW_SHA,
            {"html_url": "https://example/r", "published_at": "2026-06-22T00:00:00Z"},
            evidence,
        )
        self.assertIn("acme-widgets", body)
        self.assertIn("v1.2.3` → `v2.0.0", body)
        self.assertIn("✅ verified", body)
        self.assertIn("widgets-2.0.0.tgz", body)
        self.assertIn("gh attestation verify", body)
        # Repo-signed provenance: re-verify command must NOT add --signer-workflow.
        self.assertNotIn("--signer-workflow", body)

    def test_reverify_includes_signer_for_seam_signed(self):
        evidence = {
            "ok": True, "subject": "w.tgz", "digest": "sha256:abc",
            "checks": [
                {"predicate": "https://slsa.dev/provenance/v1",
                 "signer": "repo:acme/widgets", "ok": True, "output": "ok"},
                {"predicate": "https://ex/sast/v1",
                 "signer": "owner/.github/.github/workflows/reusable-attest-scan.yml",
                 "ok": True, "output": "ok"},
            ],
        }
        body = cu.render_pr_body(
            "acme-widgets", "acme/widgets", "v1", "v2",
            "1111111111111111111111111111111111111111", NEW_SHA, {}, evidence,
        )
        # The seam-signed predicate's re-verify line carries its signer-workflow;
        # the repo-signed one does not.
        self.assertIn("--signer-workflow owner/.github/.github/workflows/reusable-attest-scan.yml", body)




class SourceRepo(unittest.TestCase):
    def test_repo_field(self):
        self.assertEqual(cu.source_repo({"repo": "o/r"}), "o/r")

    def test_url_field(self):
        self.assertEqual(cu.source_repo(
            {"url": "https://github.com/modeled-information-format/.github.git"}),
            "modeled-information-format/.github")

    def test_url_no_suffix(self):
        self.assertEqual(cu.source_repo({"url": "https://github.com/o/r"}), "o/r")

    def test_url_trailing_slash_and_git(self):
        self.assertEqual(cu.source_repo({"url": "https://github.com/o/r.git/"}), "o/r")
        self.assertEqual(cu.source_repo({"repo": " o/r/ "}), "o/r")



class RepinAuthorNameCollision(unittest.TestCase):
    """Regression: an entry's author.name equal to another plugin's name must
    not mis-target the rewrite (the real attested-reference/attested-delivery case)."""

    MP = (
        '{\n  "name": "mp",\n  "plugins": [\n'
        '    { "name": "local-ref", "source": "./plugins/local-ref",\n'
        '      "author": { "name": "attested-delivery" } },\n'
        '    { "name": "attested-delivery",\n'
        '      "source": { "source": "git-subdir", "url": "https://github.com/o/r.git",\n'
        '        "path": ".", "ref": "v0.1.0", "sha": "%s" },\n'
        '      "author": { "name": "attested-delivery" } }\n'
        '  ]\n}\n'
    ) % ("a" * 40)

    def test_targets_correct_entry(self):
        new = "b" * 40
        out = cu.repin_text(self.MP, "attested-delivery", "a" * 40, new, "v0.1.1")
        import json as _j
        plugins = _j.loads(out)["plugins"]
        ext = [p for p in plugins if isinstance(p.get("source"), dict)][0]
        loc = [p for p in plugins if not isinstance(p.get("source"), dict)][0]
        self.assertEqual(ext["source"]["sha"], new)
        self.assertEqual(ext["source"]["ref"], "v0.1.1")
        self.assertEqual(loc["source"], "./plugins/local-ref")  # untouched

    def test_missing_plugin_raises(self):
        with self.assertRaises(ValueError):
            cu.repin_text(self.MP, "nope", "a" * 40, "b" * 40, "v0.1.1")



class SummarizeVerify(unittest.TestCase):
    JSON = (
        '[{"verificationResult": {"statement": {"predicateType": "https://slsa.dev/provenance/v1"},'
        ' "signature": {"certificate": {"buildSignerURI": "https://github.com/o/r/.github/workflows/a.yml@refs/tags/v1",'
        ' "issuer": "https://token.actions.githubusercontent.com"}}}}]'
    )

    def test_distills_signer_and_predicate(self):
        out = cu._summarize_verify(self.JSON)
        self.assertIn("https://slsa.dev/provenance/v1", out)
        self.assertIn("a.yml@refs/tags/v1", out)
        self.assertIn("token.actions.githubusercontent.com", out)

    def test_non_json_falls_back_to_raw(self):
        self.assertEqual(cu._summarize_verify("plain text"), "plain text")

    def test_empty_list_falls_back_to_raw(self):
        self.assertEqual(cu._summarize_verify("[]"), "[]")

    def test_unexpected_shape_falls_back(self):
        self.assertEqual(cu._summarize_verify('{"a": 1}'), '{"a": 1}')

    def test_skips_non_dict_records(self):
        # a list with a non-dict record must not crash; falls back when no blocks
        self.assertEqual(cu._summarize_verify('[1, 2]'), '[1, 2]')

    def test_malformed_nested_falls_back(self):
        # verificationResult (or signature/statement) being a non-dict must not crash
        for raw in ('[{"verificationResult": "x"}]',
                    '[{"verificationResult": {"signature": "x", "statement": 3}}]'):
            self.assertEqual(cu._summarize_verify(raw), raw)


if __name__ == "__main__":
    unittest.main()
