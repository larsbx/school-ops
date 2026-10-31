"""Pure installer/export tests; no Chrome/browser or elevated-policy effects."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

GUARD_ROOT = Path(__file__).resolve().parents[1] / "tools/browser/site_scoped_youtube_guard"
sys.path.insert(0, str(GUARD_ROOT))
import installer_core as core  # noqa: E402


TEST_ID = "abcdefghijklmnopabcdefghijklmnop"


def settings(**overrides):
    cfg = {
        "allowed_embed_sites": ["portal.school.org"],
        "allowed_sites": ["library.school.net"],
        "blocked_sites": ["social.example.net"],
        "mode": "blacklist",
        "channel": "web_store",
        "extension_id": TEST_ID,
        "update_url": core.WEBSTORE_URL,
        "target_os": "linux",
    }
    cfg.update(overrides)
    return cfg


class InstallerCoreTests(unittest.TestCase):
    def test_published_bundle_has_canonical_rules_policy_and_checksums(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "generated"
            core.export_bundle(settings(), target)
            self.assertTrue(target.is_dir())
            rules = json.loads((target / "extension/rules.json").read_text())
            self.assertEqual(rules, core.build(settings()))
            policy = json.loads((target / "deployment/linux-managed-policy.json").read_text())
            self.assertEqual(policy["ExtensionSettings"][TEST_ID], {
                "installation_mode": "force_installed",
                "update_url": core.WEBSTORE_URL,
            })
            gpo = json.loads((target / "deployment/extension-settings-value.json").read_text())
            self.assertEqual(gpo, policy["ExtensionSettings"])
            checksums = json.loads((target / "SHA256SUMS.json").read_text())
            for key, digest in checksums.items():
                self.assertEqual(hashlib.sha256((target / key).read_bytes()).hexdigest(), digest)
            self.assertEqual(
                core.verify_policy_bundle(target),
                (target / "deployment/linux-managed-policy.json").read_bytes(),
            )
            self.assertIn("NOT INSTALLED", (target / "deployment/README.md").read_text())

    def test_draft_bundle_can_be_published_before_an_extension_id_is_known(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "draft"
            core.export_bundle(settings(extension_id=""), target)
            self.assertTrue((target / "extension/manifest.json").exists())
            self.assertTrue((target / "extension/rules.json").exists())
            self.assertFalse((target / "deployment/linux-managed-policy.json").exists())
            self.assertFalse((target / "deployment/extension-settings-value.json").exists())
            self.assertIn("PUBLISHING PENDING", (target / "deployment/README.md").read_text())
            with self.assertRaises((ValueError, FileNotFoundError)):
                core.verify_policy_bundle(target)

    def test_invalid_inputs_produce_no_output(self):
        invalid = [
            settings(allowed_embed_sites=["approved-site.invalid"]),
            settings(allowed_embed_sites=["youtube.com"]),
            settings(allowed_embed_sites=[]),
            settings(allowed_embed_sites=["https://portal.school.org"]),
            settings(allowed_embed_sites=["*.school.org"]),
            settings(allowed_embed_sites=["127.0.0.1"]),
            settings(blocked_sites=["school.org"]),
            settings(extension_id="not-an-extension-id"),
            settings(extension_id="z" * 32),
            settings(update_url="http://malicious.test/crx"),
            settings(channel="self_hosted", update_url="http://school.org/update.xml"),
            settings(channel="self_hosted", update_url=""),
            settings(channel="self_hosted", update_url=core.WEBSTORE_URL),
            settings(channel="self_hosted", update_url="https://school.org/"),
            settings(channel="other"),
            settings(target_os="other"),
        ]
        with tempfile.TemporaryDirectory() as td:
            for i, cfg in enumerate(invalid):
                with self.subTest(cfg=cfg), self.assertRaises(ValueError):
                    core.export_bundle(cfg, Path(td) / f"invalid-{i}")
                self.assertFalse((Path(td) / f"invalid-{i}").exists())

    def test_self_hosted_managed_https_policy(self):
        with tempfile.TemporaryDirectory() as td:
            url = "https://updates.school.org/extensions/updates.xml"
            target = Path(td) / "selfhost"
            core.export_bundle(settings(channel="self_hosted", update_url=url,
                                        target_os="windows"), target)
            policy = json.loads((target / "deployment/extension-settings-value.json").read_text())
            self.assertEqual(policy[TEST_ID]["update_url"], url)
            self.assertIn("Active Directory", (target / "deployment/README.md").read_text())
            self.assertNotIn("ACTUAL_32_CHARACTER_EXTENSION_ID",
                             (target / "deployment/README.md").read_text())

    def test_draft_self_hosted_without_url(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "draft"
            core.export_bundle(settings(channel="self_hosted", extension_id="",
                                        update_url=""), target)
            self.assertFalse((target / "deployment/linux-managed-policy.json").exists())

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "bundle"
            core.export_bundle(settings(), target)
            original = (target / "extension/rules.json").read_bytes()
            with self.assertRaises(FileExistsError):
                core.export_bundle(settings(blocked_sites=["different.school.net"]), target)
            self.assertEqual(original, (target / "extension/rules.json").read_bytes())

    def test_policy_integrity_failure(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "bundle"
            core.export_bundle(settings(), target)
            policy = target / "deployment/linux-managed-policy.json"
            policy.write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "checksum"):
                core.verify_policy_bundle(target)

    def test_checksum_rewritten_rules_still_fail_semantic_validation(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "bundle"
            core.export_bundle(settings(), target)
            rules_file = target / "extension/rules.json"
            rules = json.loads(rules_file.read_text())
            rules[0]["condition"]["requestDomains"] = ["arbitrary.example.net"]
            rules_file.write_text(core.pretty_json(rules))
            sums_file = target / "SHA256SUMS.json"
            sums = json.loads(sums_file.read_text())
            sums["extension/rules.json"] = hashlib.sha256(rules_file.read_bytes()).hexdigest()
            sums_file.write_text(core.pretty_json(sums))
            with self.assertRaisesRegex(ValueError, "rules differ"):
                core.verify_policy_bundle(target)

    def test_policy_document_requires_real_id(self):
        checked = core.validate_settings(settings(extension_id=""))
        with self.assertRaisesRegex(ValueError, "extension ID"):
            core.policy_document(checked)

    def test_linux_apply_requires_privileges_on_linux(self):
        if sys.platform != "linux":
            self.skipTest("Linux-specific policy path")
        with tempfile.TemporaryDirectory() as td:
            bundle = Path(td) / "bundle"
            core.export_bundle(settings(), bundle)
            # Do not mutate /etc: mock root check and assert it is rejected.
            from unittest.mock import patch
            with patch.object(core.os, "geteuid", return_value=1000):
                with self.assertRaises(PermissionError):
                    core.apply_linux_policy(bundle)


if __name__ == "__main__":
    unittest.main()
