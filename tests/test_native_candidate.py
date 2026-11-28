"""Offline controls for native evidence admission; fixtures are not real installers."""
import io
import json
import os
import tarfile
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/browser/site_scoped_youtube_guard'))
import native_candidate as c


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.identity = c.identity('a'*40, 'b'*40, '123', '1')
        for runner, (system, label, ext) in c.PLATFORMS.items():
            folder = self.root / runner
            folder.mkdir()
            archive = folder / (c.APP + '-' + label + '-unsigned' + ext)
            archive.write_bytes(b'not an installer: test only')
            smoke = dict(status='passed', frozen=True)
            release = dict(status='passed', commands={'key-id':'passed', 'prepare':'passed', 'sign':'passed', 'missing-key':'failed'}, privateKeysRetained=False, policyApplied=False, remotePublication=False)
            report = dict(schema=1, status='unsigned_native_bundle_built', sourceCommit='a'*40, platform=system, architecture='test', python='3.12.16', pyinstaller='6.22.3', archive=archive.name, archiveSha256=c.digest(archive), nativeSmoke=smoke, nativeReleaseSmoke=release)
            for name, value in [('native-smoke.json', smoke), ('native-release-smoke.json', release), ('build-report.json', report), ('archive-smoke.json', smoke)]:
                c.write(folder / name, value)
            (folder / 'SHA256SUMS.txt').write_text(c.digest(archive)+'  '+archive.name+'\n')
            (folder / 'START_HERE.txt').write_text('fixture')
            if system == 'Linux':
                (folder / 'source-gui-smoke.txt').write_text(c.GUI_PASS+'\n'+c.GUI_SAFE+'\n')
            c.write(folder / 'candidate.json', c.validate(folder, runner, self.identity, sealed=False))

    def test_complete_set(self):
        first = c.index(self.root, self.identity)
        self.assertEqual(first, c.index(self.root, self.identity, verify=True))

    def test_missing_platform(self):
        (self.root / 'macos-15').rename(self.root / 'unexpected')
        with self.assertRaisesRegex(ValueError, 'platform set'):
            c.index(self.root, self.identity)

    def test_wrong_attempt(self):
        with self.assertRaisesRegex(ValueError, 'manifest mismatch'):
            c.index(self.root, dict(self.identity, runAttempt='2'))

    def test_wrong_revision(self):
        with self.assertRaisesRegex(ValueError, 'source commit'):
            c.index(self.root, dict(self.identity, sourceCommit='c'*40))

    def test_wrong_tree(self):
        with self.assertRaisesRegex(ValueError, 'manifest mismatch'):
            c.index(self.root, dict(self.identity, sourceTree='c'*40))

    def test_archive_tampering(self):
        next((self.root / 'ubuntu-24.04').glob('*.tar.gz')).write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'archive mismatch'):
            c.index(self.root, self.identity)

    def test_log_missing(self):
        (self.root / 'ubuntu-24.04' / 'source-gui-smoke.txt').unlink()
        with self.assertRaisesRegex(ValueError, 'payload'):
            c.index(self.root, self.identity)

    def test_gui_failure(self):
        (self.root / 'ubuntu-24.04' / 'source-gui-smoke.txt').write_text('failed')
        with self.assertRaisesRegex(ValueError, 'GUI smoke'):
            c.index(self.root, self.identity)

    def test_archive_replay_failure(self):
        (self.root / 'windows-2025' / 'archive-smoke.json').write_text('{"status":"failed"}')
        with self.assertRaisesRegex(ValueError, 'archive smoke'):
            c.index(self.root, self.identity)

    def test_nonregular_or_extra_payload(self):
        (self.root / 'windows-2025' / 'extra.txt').write_text('extra')
        with self.assertRaisesRegex(ValueError, 'payload'):
            c.index(self.root, self.identity)

    def test_index_tampering(self):
        c.index(self.root, self.identity)
        (self.root / 'INDEX.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'index mismatch'):
            c.index(self.root, self.identity, verify=True)

    def test_wrong_checkout_rejects_before_executing_archive(self):
        with patch.object(c, 'git', return_value='f'*40), patch.object(c, 'archive_smoke') as smoke:
            with self.assertRaisesRegex(ValueError, 'wrong checkout'):
                c.seal(self.root / 'windows-2025', 'windows-2025', self.identity)
            smoke.assert_not_called()

    def test_modified_source_rejects_before_archive(self):
        with patch.object(c, 'git', side_effect=['a'*40, 'b'*40, ' M wizard.py']), patch.object(c, 'archive_smoke') as smoke:
            with self.assertRaisesRegex(ValueError, 'tracked source modified'):
                c.seal(self.root / 'windows-2025', 'windows-2025', self.identity)
            smoke.assert_not_called()

    @unittest.skipUnless(os.name == 'posix', 'POSIX executable test fixture')
    def test_archive_replay_executes_extracted_fixture(self):
        folder = self.root / 'ubuntu-24.04'
        archive = next(folder.glob('*.tar.gz'))
        # Deliberately synthetic executable: tests extraction, cwd, and report handling only.
        script = b"""#!/bin/sh
[ \"$1\" = --self-test ] || exit 1
printf '%s\\n' '{\"status\":\"passed\",\"frozen\":true}' > \"$2\"
"""
        with tarfile.open(archive, 'w:gz') as t:
            member = tarfile.TarInfo(c.APP + '/' + c.APP)
            member.size = len(script)
            member.mode = 0o755
            t.addfile(member, io.BytesIO(script))
        report = c.read(folder / 'build-report.json')
        report['archiveSha256'] = c.digest(archive)
        (folder / 'build-report.json').write_text(json.dumps(report))
        (folder / 'archive-smoke.json').unlink()
        c.archive_smoke(folder, 'ubuntu-24.04')
        self.assertEqual(c.read(folder / 'archive-smoke.json'), c.read(folder / 'native-smoke.json'))

    def test_identity_format(self):
        for args in [('main', 'b'*40, '1', '1'), ('a'*40, 'b'*40, '0', '1')]:
            with self.assertRaises(ValueError):
                c.identity(*args)


if __name__ == '__main__':
    unittest.main()
