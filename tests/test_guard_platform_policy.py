"""Disposable policy/registry tests. Never mutate /etc or a real registry hive."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import plistlib
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid


ROOT = Path(__file__).resolve().parents[1] / "tools/browser/site_scoped_youtube_guard"
sys.path.insert(0, str(ROOT))
import platform_policy as policy  # noqa: E402

EXTENSION_ID = "abcdefghijklmnopabcdefghijklmnop"
OTHER_ID = "p" * 32
SETTINGS = {
    "installation_mode": "force_installed",
    "update_url": "https://clients2.google.com/service/update2/crx",
}
CONTENT = json.dumps({"ExtensionSettings": {EXTENSION_ID: SETTINGS}}).encode("utf-8")


class PolicyDocumentTests(unittest.TestCase):
    def test_merge_preserves_wildcard_unrelated_fields_and_inputs(self):
        existing = {"*": {"installation_mode": "blocked"},
                    OTHER_ID: {"installation_mode": "allowed", "blocked_permissions": ["usb"]}}
        expected = json.loads(json.dumps(existing))
        result = policy.merge_extension_settings(existing, {EXTENSION_ID: SETTINGS})
        self.assertEqual({key: result[key] for key in existing}, expected)
        self.assertEqual(existing, expected)
        result[OTHER_ID]["blocked_permissions"].append("serial")
        self.assertEqual(existing, expected)

    def test_merge_is_idempotent_and_rejects_same_id_conflicts(self):
        existing = {EXTENSION_ID: dict(SETTINGS), OTHER_ID: {"installation_mode": "allowed"}}
        self.assertEqual(policy.merge_extension_settings(existing, {EXTENSION_ID: SETTINGS}), existing)
        changed = dict(SETTINGS, installation_mode="blocked")
        with self.assertRaisesRegex(ValueError, "different policy"):
            policy.merge_extension_settings({EXTENSION_ID: changed}, {EXTENSION_ID: SETTINGS})
        self.assertEqual(changed["installation_mode"], "blocked")

    def test_unexpected_incoming_settings_rejected(self):
        for value in ({"*": SETTINGS}, {}, {EXTENSION_ID: {"installation_mode": "blocked"}},
                      {EXTENSION_ID: dict(SETTINGS, override_update_url=False)},
                      {EXTENSION_ID: dict(SETTINGS, update_url="http://updates.school.org/a.xml")},
                      {EXTENSION_ID: dict(SETTINGS, update_url="https://x.school.org/a.xml?secret=1")},
                      {EXTENSION_ID: dict(SETTINGS, update_url="https://x.school.org:bad/a.xml")},
                      {EXTENSION_ID: dict(SETTINGS, unrelated="anything")}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                policy.merge_extension_settings({}, value)

    def test_self_hosted_override_accepted(self):
        settings = dict(SETTINGS, update_url="https://updates.school.org/a.xml", override_update_url=True)
        self.assertEqual(policy.merge_extension_settings({}, {EXTENSION_ID: settings}),
                         {EXTENSION_ID: settings})

    def test_document_rejects_duplicates_and_extra_policy(self):
        for content in (b'{"ExtensionSettings":{},"ExtensionSettings":{}}',
                        json.dumps({"ExtensionSettings": {EXTENSION_ID: SETTINGS},
                                    "IncognitoModeAvailability": 1}),
                        "[]"):
            with self.subTest(content=content), self.assertRaises(ValueError):
                policy.macos_profile(content)

    def test_macos_profile_roundtrip_and_stable_payload_identity(self):
        profile = plistlib.loads(policy.macos_profile(CONTENT))
        self.assertEqual(profile["PayloadType"], "Configuration")
        self.assertEqual(profile["PayloadScope"], "System")
        preferences = profile["PayloadContent"][0]
        self.assertEqual(preferences["PayloadType"], "com.apple.ManagedClient.preferences")
        value = preferences["PayloadContent"]["com.google.Chrome"]["Forced"][0]
        self.assertEqual(value["mcx_preference_settings"], json.loads(CONTENT))
        changed = json.dumps({"ExtensionSettings": {EXTENSION_ID: dict(
            SETTINGS, update_url="https://updates.school.org/a.xml", override_update_url=True)}})
        second = plistlib.loads(policy.macos_profile(changed))
        self.assertEqual(second["PayloadUUID"], profile["PayloadUUID"])
        self.assertEqual(second["PayloadContent"][0]["PayloadUUID"], preferences["PayloadUUID"])
        self.assertNotEqual(profile["PayloadUUID"], preferences["PayloadUUID"])

    def test_root_control_checks_owner_mode_and_object_type(self):
        policy._assert_root_controlled(SimpleNamespace(st_uid=0, st_mode=stat.S_IFDIR | 0o755), True)
        policy._assert_root_controlled(SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o644))
        for owner, mode, directory in (
                (1000, stat.S_IFDIR | 0o755, True),
                (0, stat.S_IFDIR | 0o775, True),
                (0, stat.S_IFDIR | 0o777, True),
                (0, stat.S_IFREG | 0o664, False),
                (0, stat.S_IFLNK | 0o777, False),
                (0, stat.S_IFIFO | 0o644, False)):
            with self.subTest(owner=owner, mode=mode), self.assertRaises(PermissionError):
                policy._assert_root_controlled(SimpleNamespace(st_uid=owner, st_mode=mode), directory)


@unittest.skipUnless(sys.platform == "linux", "Linux descriptor-based path checks")
class LinuxPolicyTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.folder = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.target = self.folder / "chrome/policies/managed/school-ops-youtube-guard.json"
        self.target.parent.mkdir(parents=True)
        self.stack.enter_context(patch.object(policy, "LINUX_MANAGED_PATH", self.target))
        self.stack.enter_context(patch.object(policy.platform, "system", return_value="Linux"))
        self.stack.enter_context(patch.object(policy.os, "geteuid", return_value=0))
        # The test process owns a temporary tree, not root's policy directories.
        # Keep real type checks and all descriptor/O_NOFOLLOW behavior. Owner and
        # permission enforcement itself is tested separately above.
        actual_check = policy._assert_root_controlled
        def temporary_root(info, directory=False):
            actual_check(SimpleNamespace(st_uid=0, st_mode=info.st_mode & ~0o022), directory)
        self.root_check = self.stack.enter_context(
            patch.object(policy, "_assert_root_controlled", side_effect=temporary_root))

    @property
    def receipt(self):
        return self.target.parent / policy._linux_receipt_name(self.target)

    def test_install_reapply_remove_and_preserve_other_policy(self):
        unrelated = self.target.parent / "other.json"
        unrelated.write_text('{"IncognitoModeAvailability":1}')
        self.assertEqual(policy.apply_linux_policy_content(CONTENT), "installed")
        self.assertEqual(self.target.read_bytes(), CONTENT)
        self.assertTrue(self.receipt.exists())
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o644)
        self.assertEqual(policy.apply_linux_policy_content(CONTENT), "already_configured")
        self.assertEqual(policy.remove_linux_policy_content(CONTENT), "removed")
        self.assertFalse(self.target.exists())
        self.assertFalse(self.receipt.exists())
        self.assertEqual(unrelated.read_text(), '{"IncognitoModeAvailability":1}')
        self.assertEqual(policy.remove_linux_policy_content(CONTENT), "already_absent")

    def test_identical_preexisting_file_does_not_become_installer_owned(self):
        self.target.write_bytes(CONTENT)
        self.assertEqual(policy.apply_linux_policy_content(CONTENT), "already_configured")
        self.assertFalse(self.receipt.exists())
        self.assertEqual(policy.remove_linux_policy_content(CONTENT), "not_owned")
        self.assertEqual(self.target.read_bytes(), CONTENT)

    def test_existing_changed_policy_is_preserved(self):
        self.target.write_bytes(b'{"ExtensionSettings":{}}')
        with self.assertRaisesRegex(ValueError, "differs"):
            policy.apply_linux_policy_content(CONTENT)
        self.assertEqual(self.target.read_bytes(), b'{"ExtensionSettings":{}}')
        self.assertFalse(self.receipt.exists())

    def test_changed_installed_policy_or_receipt_cannot_be_removed(self):
        policy.apply_linux_policy_content(CONTENT)
        self.target.write_bytes(CONTENT + b" ")
        with self.assertRaisesRegex(ValueError, "changed"):
            policy.remove_linux_policy_content(CONTENT)
        self.assertTrue(self.target.exists())
        self.target.write_bytes(CONTENT)
        self.receipt.write_text("{}")
        with self.assertRaisesRegex(ValueError, "receipt differs"):
            policy.remove_linux_policy_content(CONTENT)
        self.assertTrue(self.target.exists())

    def test_competing_or_malformed_policy_prevents_installation(self):
        other = self.target.parent / "existing.json"
        for content in ('{"ExtensionSettings":{"*":{"installation_mode":"blocked"}}}',
                        '{"broken":', '[]', '{"x":1,"x":2}', '{"x":NaN}'):
            other.write_text(content)
            with self.subTest(content=content), self.assertRaises(ValueError):
                policy.apply_linux_policy_content(CONTENT)
            self.assertFalse(self.target.exists())
            self.assertFalse(self.receipt.exists())

    def test_ancestor_symlink_is_rejected(self):
        alternate = self.folder / "alternate"
        alternate.mkdir()
        link = self.folder / "linked"
        link.symlink_to(alternate, target_is_directory=True)
        target = link / self.target.name
        with patch.object(policy, "LINUX_MANAGED_PATH", target), self.assertRaises(OSError):
            policy.apply_linux_policy_content(CONTENT)
        self.assertEqual(list(alternate.iterdir()), [])

    def test_final_policy_and_other_policy_symlinks_are_rejected(self):
        outside = self.folder / "outside"
        outside.write_bytes(CONTENT)
        self.target.symlink_to(outside)
        with self.assertRaises(OSError):
            policy.apply_linux_policy_content(CONTENT)
        self.assertEqual(outside.read_bytes(), CONTENT)
        self.target.unlink()
        (self.target.parent / "other.json").symlink_to(outside)
        with self.assertRaises(OSError):
            policy.apply_linux_policy_content(CONTENT)
        self.assertFalse(self.target.exists())

    def test_every_opened_ancestor_is_checked(self):
        with patch.object(policy, "_assert_root_controlled", side_effect=PermissionError("root-controlled")):
            with self.assertRaisesRegex(PermissionError, "root-controlled"):
                policy.apply_linux_policy_content(CONTENT)
        self.assertFalse(self.target.exists())
        policy.apply_linux_policy_content(CONTENT)
        self.assertGreaterEqual(sum(call.kwargs.get("directory", False)
                                    for call in self.root_check.call_args_list),
                                len(self.target.parent.parts))

    def test_receipt_failure_rolls_back_new_policy(self):
        original = policy._exclusive_file
        def fail_receipt(directory, name, content):
            if name.endswith(".receipt"):
                raise OSError("receipt write failure")
            return original(directory, name, content)
        with patch.object(policy, "_exclusive_file", side_effect=fail_receipt):
            with self.assertRaisesRegex(OSError, "receipt write failure"):
                policy.apply_linux_policy_content(CONTENT)
        self.assertFalse(self.target.exists())
        self.assertFalse(self.receipt.exists())
        self.assertFalse(list(self.target.parent.glob(".schoolops-policy-*")))

    def test_privileges_platform_and_canonical_target_are_required(self):
        with patch.object(policy.os, "geteuid", return_value=1000), self.assertRaises(PermissionError):
            policy.apply_linux_policy_content(CONTENT)
        with patch.object(policy.platform, "system", return_value="Darwin"), self.assertRaises(RuntimeError):
            policy.apply_linux_policy_content(CONTENT)
        with self.assertRaisesRegex(ValueError, "noncanonical"):
            policy.apply_linux_policy_content(CONTENT, self.folder / "arbitrary.json")
        self.assertFalse(self.target.exists())

    def test_orphan_receipt_is_not_reused_to_claim_ownership(self):
        self.receipt.write_bytes(policy._receipt(CONTENT))
        with self.assertRaisesRegex(ValueError, "orphaned"):
            policy.apply_linux_policy_content(CONTENT)
        self.assertFalse(self.target.exists())
        self.assertEqual(policy.remove_linux_policy_content(CONTENT), "already_absent")
        self.assertFalse(self.receipt.exists())


class FakeRegistry:
    HKEY_LOCAL_MACHINE = "HKLM"
    KEY_READ = 1
    KEY_SET_VALUE = 2
    KEY_WOW64_64KEY = 256
    REG_SZ = 1

    def __init__(self):
        self.values = {}
        self.accesses = []

    class Key:
        def __init__(self, path):
            self.path = path
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False

    def OpenKey(self, hive, path, reserved, access):
        self.accesses.append((hive, path, access))
        if not any(key[0] == path for key in self.values):
            raise FileNotFoundError(path)
        return self.Key(path)

    def CreateKeyEx(self, hive, path, reserved, access):
        self.accesses.append((hive, path, access))
        return self.Key(path)

    def QueryValueEx(self, key, name):
        try:
            return self.values[(key.path, name)]
        except KeyError as exc:
            raise FileNotFoundError(name) from exc

    def SetValueEx(self, key, name, reserved, kind, value):
        self.values[(key.path, name)] = (value, kind)

    def DeleteValue(self, key, name):
        try:
            del self.values[(key.path, name)]
        except KeyError as exc:
            raise FileNotFoundError(name) from exc


class WindowsPolicyTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.registry = FakeRegistry()
        self.stack.enter_context(patch.object(policy, "winreg", self.registry))
        self.stack.enter_context(patch.object(policy.platform, "system", return_value="Windows"))
        self.stack.enter_context(patch.object(policy, "_windows_admin", return_value=True))

    @property
    def key(self):
        return (policy.WINDOWS_POLICY_KEY, policy.WINDOWS_POLICY_VALUE)

    @property
    def receipt_key(self):
        return (policy.WINDOWS_RECEIPT_KEY, EXTENSION_ID)

    def set_policy(self, value):
        self.registry.values[self.key] = (json.dumps(value), self.registry.REG_SZ)

    def get_policy(self):
        return json.loads(self.registry.values[self.key][0])

    def test_install_and_rollback_preserve_current_unrelated_entries_in_64bit_hklm(self):
        existing = {"*": {"installation_mode": "blocked"}, OTHER_ID: {"installation_mode": "allowed"}}
        self.set_policy(existing)
        self.assertEqual(policy.apply_windows_policy_content(CONTENT), "installed")
        self.assertEqual(self.get_policy(), {**existing, EXTENSION_ID: SETTINGS})
        self.assertIn(self.receipt_key, self.registry.values)
        self.assertEqual(policy.apply_windows_policy_content(CONTENT), "already_configured")
        # A later unrelated administrator edit must survive rollback.
        latest = self.get_policy()
        latest[OTHER_ID]["blocked_permissions"] = ["usb"]
        self.set_policy(latest)
        self.assertEqual(policy.remove_windows_policy_content(CONTENT), "removed")
        del latest[EXTENSION_ID]
        self.assertEqual(self.get_policy(), latest)
        self.assertNotIn(self.receipt_key, self.registry.values)
        self.assertEqual(policy.remove_windows_policy_content(CONTENT), "already_absent")
        self.assertTrue(all(hive == "HKLM" and access & self.registry.KEY_WOW64_64KEY
                            for hive, _, access in self.registry.accesses))

    def test_new_policy_value_removed_when_last_owned_entry_removed(self):
        self.assertEqual(policy.apply_windows_policy_content(CONTENT), "installed")
        self.assertEqual(policy.remove_windows_policy_content(CONTENT), "removed")
        self.assertNotIn(self.key, self.registry.values)

    def test_preexisting_identical_entry_is_not_owned_or_removed(self):
        self.set_policy({EXTENSION_ID: SETTINGS})
        self.assertEqual(policy.apply_windows_policy_content(CONTENT), "already_configured")
        self.assertNotIn(self.receipt_key, self.registry.values)
        self.assertEqual(policy.remove_windows_policy_content(CONTENT), "not_owned")
        self.assertEqual(self.get_policy(), {EXTENSION_ID: SETTINGS})

    def test_conflicting_entry_and_malformed_registry_value_remain_unchanged(self):
        for raw, kind in ((json.dumps({EXTENSION_ID: {"installation_mode": "blocked"}}), 1),
                          ("{broken", 1), ("[]", 1), ("{}", 7)):
            self.registry.values[self.key] = (raw, kind)
            with self.subTest(raw=raw, kind=kind), self.assertRaises(ValueError):
                policy.apply_windows_policy_content(CONTENT)
            self.assertEqual(self.registry.values[self.key], (raw, kind))
            self.assertNotIn(self.receipt_key, self.registry.values)

    def test_changed_owned_entry_and_receipt_cannot_be_removed(self):
        policy.apply_windows_policy_content(CONTENT)
        self.set_policy({EXTENSION_ID: dict(SETTINGS, override_update_url=True)})
        with self.assertRaisesRegex(ValueError, "changed"):
            policy.remove_windows_policy_content(CONTENT)
        self.set_policy({EXTENSION_ID: SETTINGS})
        self.registry.values[self.receipt_key] = ("{}", 1)
        with self.assertRaisesRegex(ValueError, "receipt differs"):
            policy.remove_windows_policy_content(CONTENT)
        self.assertEqual(self.get_policy(), {EXTENSION_ID: SETTINGS})

    def test_receipt_write_failure_restores_previous_policy(self):
        previous = {OTHER_ID: {"installation_mode": "allowed"}}
        self.set_policy(previous)
        original = policy._win_write
        def fail_receipt(path, name, value):
            if path == policy.WINDOWS_RECEIPT_KEY:
                raise OSError("receipt write failure")
            return original(path, name, value)
        with patch.object(policy, "_win_write", side_effect=fail_receipt):
            with self.assertRaisesRegex(OSError, "receipt write failure"):
                policy.apply_windows_policy_content(CONTENT)
        self.assertEqual(self.get_policy(), previous)
        self.assertNotIn(self.receipt_key, self.registry.values)

    def test_policy_reread_detects_concurrent_change_before_write(self):
        original = policy._win_read
        count = 0
        changed = {OTHER_ID: {"installation_mode": "allowed"}}
        def change_before_write(path, name):
            nonlocal count
            if path == policy.WINDOWS_POLICY_KEY:
                count += 1
                if count == 2:
                    self.set_policy(changed)
            return original(path, name)
        with patch.object(policy, "_win_read", side_effect=change_before_write):
            with self.assertRaisesRegex(ValueError, "changed during"):
                policy.apply_windows_policy_content(CONTENT)
        self.assertEqual(self.get_policy(), changed)
        self.assertNotIn(self.receipt_key, self.registry.values)

    def test_receipt_failure_does_not_undo_a_later_administrator_edit(self):
        original = policy._win_write
        later = {EXTENSION_ID: SETTINGS, OTHER_ID: {"installation_mode": "allowed"}}
        def fail_after_edit(path, name, value):
            if path == policy.WINDOWS_RECEIPT_KEY:
                self.set_policy(later)
                raise OSError("receipt write failure after edit")
            return original(path, name, value)
        with patch.object(policy, "_win_write", side_effect=fail_after_edit):
            with self.assertRaisesRegex(OSError, "after edit"):
                policy.apply_windows_policy_content(CONTENT)
        self.assertEqual(self.get_policy(), later)
        self.assertNotIn(self.receipt_key, self.registry.values)
        self.assertEqual(policy.remove_windows_policy_content(CONTENT), "not_owned")

    def test_admin_and_windows_required(self):
        with patch.object(policy, "_windows_admin", return_value=False), self.assertRaises(PermissionError):
            policy.apply_windows_policy_content(CONTENT)
        with patch.object(policy.platform, "system", return_value="Linux"), self.assertRaises(RuntimeError):
            policy.apply_windows_policy_content(CONTENT)
        self.assertEqual(self.registry.values, {})


@unittest.skipUnless(sys.platform == "win32", "Actual disposable Windows registry integration")
class RealWindowsRegistryTests(unittest.TestCase):
    def test_real_registry_cycle_in_disposable_hkcu_key(self):
        """Exercise winreg itself, redirected only to a unique HKCU test subtree."""
        import winreg
        test_root = r"Software\SchoolOps-Policy-Test-" + uuid.uuid4().hex
        test_policy = test_root + r"\Policy"
        test_receipts = test_root + r"\Receipts"
        hkcu = winreg.HKEY_CURRENT_USER

        def cleanup(path):
            try:
                with winreg.OpenKey(hkcu, path, 0,
                                    winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                    children = []
                    index = 0
                    while True:
                        try:
                            children.append(winreg.EnumKey(key, index))
                        except OSError:
                            break
                        index += 1
            except FileNotFoundError:
                return
            for child in children:
                cleanup(path + "\\" + child)
            winreg.DeleteKeyEx(hkcu, path, winreg.KEY_WOW64_64KEY, 0)

        try:
            with (patch.object(winreg, "HKEY_LOCAL_MACHINE", hkcu),
                  patch.object(policy, "WINDOWS_POLICY_KEY", test_policy),
                  patch.object(policy, "WINDOWS_RECEIPT_KEY", test_receipts),
                  patch.object(policy, "_windows_admin", return_value=True)):
                existing = {"*": {"installation_mode": "blocked"},
                            OTHER_ID: {"installation_mode": "allowed"}}
                policy._win_write(test_policy, policy.WINDOWS_POLICY_VALUE, json.dumps(existing))
                self.assertEqual(policy.apply_windows_policy_content(CONTENT), "installed")
                read_policy = lambda: json.loads(policy._win_read(test_policy, policy.WINDOWS_POLICY_VALUE))
                self.assertEqual(read_policy(), {**existing, EXTENSION_ID: SETTINGS})
                self.assertIsNotNone(policy._win_read(test_receipts, EXTENSION_ID))
                self.assertEqual(policy.apply_windows_policy_content(CONTENT), "already_configured")
                changed = read_policy()
                changed[OTHER_ID]["blocked_permissions"] = ["usb"]
                policy._win_write(test_policy, policy.WINDOWS_POLICY_VALUE, json.dumps(changed))
                self.assertEqual(policy.remove_windows_policy_content(CONTENT), "removed")
                del changed[EXTENSION_ID]
                self.assertEqual(read_policy(), changed)
                self.assertIsNone(policy._win_read(test_receipts, EXTENSION_ID))
                self.assertEqual(policy.remove_windows_policy_content(CONTENT), "already_absent")
        finally:
            cleanup(test_root)


if __name__ == "__main__":
    unittest.main()
