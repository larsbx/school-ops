"""Native SchoolOps wizard packaging contracts; no GUI or device install."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / "tools/browser/site_scoped_youtube_guard"
sys.path.insert(0, str(ROOT))
import package_native as native  # noqa: E402
try:
    import wizard  # noqa: E402
except ImportError:
    # A curriculum-only CI runner may not include optional GUI/Tk libraries.
    # The dedicated native packaging jobs still require the actual GUI build.
    wizard = None


class NativeWizardTests(unittest.TestCase):
    @unittest.skipIf(wizard is None, "Optional tkinter GUI libraries not installed")
    def test_headless_source_self_test_exports_valid_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "smoke.json"
            wizard._package_self_test(target)
            report = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "passed")
            self.assertFalse(report["frozen"])
            self.assertEqual(report["chromeMinimum"], "145")
            self.assertEqual(report["ruleCount"], 3)
            self.assertIn("NO GUI", report["scope"])
            with self.assertRaises(FileExistsError):
                wizard._package_self_test(target)

    def test_native_build_requires_explicit_platform_and_bundled_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp)
            for system in ("Linux", "Darwin", "Windows"):
                with self.subTest(system=system):
                    args = native.build_command(sys.executable, scratch, system)
                    self.assertIn("--windowed", args)
                    self.assertIn("--clean", args)
                    self.assertIn("--add-data", args)
                    index = args.index("--add-data")
                    self.assertIn("manifest.json", args[index + 1])
                    self.assertTrue(args[-1].endswith("wizard.py"))
                    self.assertNotIn("--uac-admin", args)
                    self.assertEqual("--onedir" in args, system == "Darwin")
                    self.assertEqual("--onefile" in args, system != "Darwin")
                    program = native.packaged_executable(scratch, system)
                    self.assertIn(native.APP, str(program))
            with self.assertRaises(ValueError):
                native.build_command(sys.executable, scratch, "OtherOS")
            with self.assertRaises(ValueError):
                native.packaged_executable(scratch, "OtherOS")

    def test_checksum_is_content_based(self):
        with tempfile.TemporaryDirectory() as tmp:
            item = Path(tmp) / "content.bin"
            item.write_bytes(b"schoolops")
            digest1 = native.sha256(item)
            self.assertEqual(len(digest1), 64)
            item.write_bytes(b"schoolops changed")
            self.assertNotEqual(digest1, native.sha256(item))

    def test_no_native_output_may_be_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "already-exists"
            folder.mkdir()
            with self.assertRaises(FileExistsError):
                native.package(folder)


if __name__ == "__main__":
    unittest.main()
