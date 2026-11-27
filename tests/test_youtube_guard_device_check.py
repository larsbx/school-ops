"""Read-only machine policy diagnosis contracts.

No tests write to HKLM, /etc, MDM or Chrome. A matching machine snapshot is
NEVER asserted to establish effective managed Chrome policy or YouTube playback.
"""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "tools/browser/site_scoped_youtube_guard"
sys.path.insert(0, str(ROOT))
import device_check as check  # noqa: E402
import installer_core as core  # noqa: E402


ID = "abcdefghijklmnopabcdefghijklmnop"
EXPECTED = {"ExtensionSettings": {ID: {
    "installation_mode": "force_installed",
    "update_url": core.WEBSTORE_URL,
}}}


def published(os_name="linux"):
    cfg = {
        "allowed_embed_sites": ["school.example.org"],
        "mode": "blacklist",
        "allowed_sites": [],
        "blocked_sites": [],
        "channel": "web_store",
        "extension_id": ID,
        "update_url": core.WEBSTORE_URL,
        "extension_version": "0.1.0",
        "target_os": os_name,
        "publication_confirmed": True,
    }
    cfg["published_extension_sha256"] = core.extension_digest(core.validate_settings(cfg))
    return cfg


class PureLinuxPolicyClassification(unittest.TestCase):
    def test_expected_local_file_matches_and_ignores_unrelated_policies(self):
        self.assertEqual(check.classify_linux({
            check.OWN_LINUX_NAME: json.dumps(EXPECTED).encode(),
            "another-policy.json": b'{"HomepageLocation":"https://example.org"}',
        }, EXPECTED), "matching")

    def test_missing_or_changed_is_not_a_pass(self):
        self.assertEqual(check.classify_linux({}, EXPECTED), "missing")
        self.assertEqual(check.classify_linux({
            check.OWN_LINUX_NAME: b'{"ExtensionSettings": {}}',
        }, EXPECTED), "different")

    def test_other_extension_settings_is_conflict_even_if_ours_matches(self):
        self.assertEqual(check.classify_linux({
            check.OWN_LINUX_NAME: json.dumps(EXPECTED),
            "another-policy.json": b'{"ExtensionSettings": {"*": {"installation_mode": "blocked"}}}',
        }, EXPECTED), "conflicting")
        self.assertEqual(check.classify_linux({
            "another-policy.json": json.dumps(EXPECTED),
        }, EXPECTED), "conflicting")

    def test_malformed_or_duplicate_json_fails_closed(self):
        values = (b"{broken", b'{"HomepageLocation":"a","HomepageLocation":"b"}',
                  b'["not an object"]', b"\xff")
        for raw in values:
            with self.subTest(raw=raw):
                self.assertEqual(check.classify_linux({
                    check.OWN_LINUX_NAME: json.dumps(EXPECTED),
                    "uncertain.json": raw,
                }, EXPECTED), "uninspectable")
        with self.assertRaises(ValueError):
            check.classify_linux({"../escape.json": b"{}"}, EXPECTED)

    def test_readonly_os_directory_view(self):
        inventory = {check.OWN_LINUX_NAME: json.dumps(EXPECTED).encode()}
        with patch.object(check.platform_policy, "_policy_directory", return_value=22) as open_dir, \
             patch.object(check.os, "listdir", return_value=list(inventory)) as ls, \
             patch.object(check.platform_policy, "_read_at", side_effect=lambda _fd, n: inventory[n]), \
             patch.object(check.os, "close") as close:
            self.assertEqual(check.inspect_linux(EXPECTED), "matching")
        open_dir.assert_called_once_with(check.platform_policy.LINUX_MANAGED_PATH, create=False)
        ls.assert_called_once_with(22)
        close.assert_called_once_with(22)
        with patch.object(check.platform_policy, "_policy_directory", return_value=None):
            self.assertEqual(check.inspect_linux(EXPECTED), "missing")


class MachineSnapshotTests(unittest.TestCase):
    def test_windows_registry_snapshot_never_writes(self):
        with patch.object(check.platform_policy, "_windows_snapshot",
                          return_value=(None, {ID: EXPECTED["ExtensionSettings"][ID]})) as reader:
            self.assertEqual(check.inspect_windows(EXPECTED), "matching")
            reader.assert_called_once_with()
        with patch.object(check.platform_policy, "_windows_snapshot", return_value=(None, {})):
            self.assertEqual(check.inspect_windows(EXPECTED), "missing")

    def test_real_prepared_bundle_is_checked_before_policy_inspection(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / "published"
            core.export_bundle(published(), bundle)
            with patch.object(check, "inspect_linux", return_value="matching") as inspector:
                report = check.check_bundle(bundle, system="Linux")
            inspector.assert_called_once()
            self.assertEqual(report["scope"], "read_only_local_machine_policy")
            self.assertEqual(report["local_policy_status"], "matching")
            self.assertIs(report["local_policy_matches_expected"], True)
            self.assertEqual(report["extension_id"], ID)
            self.assertEqual(report["tamper_resistance"], "not_established")
            self.assertEqual(report["chrome_effective_policy"], "not_verified")
            self.assertEqual(report["extension_installed_and_locked"], "not_verified")
            self.assertEqual(report["youtube_playback_and_blocking"], "not_verified")
            self.assertNotIn("school.example.org", json.dumps(report))
            self.assertIn("remain UNVERIFIED", check.format_result(report))

    def test_wrong_platform_never_inspects_machine_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / "published"
            core.export_bundle(published(), bundle)
            with patch.object(check, "inspect_linux") as linux, \
                 patch.object(check, "inspect_windows") as windows:
                result = check.check_bundle(bundle, system="Darwin")
            self.assertEqual(result["local_policy_status"], "wrong_target")
            self.assertIsNone(result["local_policy_matches_expected"])
            linux.assert_not_called()
            windows.assert_not_called()

    def test_macos_and_chromeos_not_misrepresented_as_inspected(self):
        with tempfile.TemporaryDirectory() as temp:
            for target, system in (("macos", "Darwin"), ("chromeos", "ChromeOS")):
                bundle = Path(temp) / target
                core.export_bundle(published(target), bundle)
                result = check.check_bundle(bundle, system=system)
                self.assertEqual(result["local_policy_status"], "unsupported")
                self.assertIsNone(result["local_policy_matches_expected"])

    def test_unreadable_policy_must_not_be_reported_missing_or_matching(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / "published"
            core.export_bundle(published(), bundle)
            with patch.object(check, "inspect_linux", side_effect=PermissionError("not readable")):
                report = check.check_bundle(bundle, system="Linux")
            self.assertEqual(report["local_policy_status"], "uninspectable")
            self.assertIsNone(report["local_policy_matches_expected"])

    def test_mutated_bundle_fails_before_device_check(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / "published"
            core.export_bundle(published(), bundle)
            (bundle / "deployment/linux-managed-policy.json").write_text("{}")
            with patch.object(check, "inspect_linux") as inspector:
                with self.assertRaises(ValueError):
                    check.check_bundle(bundle, system="Linux")
                inspector.assert_not_called()

    def test_cli_creates_report_exclusively_and_stays_non_success_for_missing_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / "published"
            core.export_bundle(published(), bundle)
            report = Path(temp) / "report.json"
            with patch.object(check, "inspect_linux", return_value="missing"), \
                 patch.object(check.platform, "system", return_value="Linux"), \
                 patch("sys.stdout", new_callable=io.StringIO) as stdout:
                self.assertEqual(check.main([str(bundle), "--report", str(report)]), 1)
                self.assertEqual(check.main([str(bundle), "--report", str(report)]), 2)
                self.assertIn("UNVERIFIED", stdout.getvalue())
            data = json.loads(report.read_text())
            self.assertEqual(data["local_policy_status"], "missing")


if __name__ == "__main__":
    unittest.main()
