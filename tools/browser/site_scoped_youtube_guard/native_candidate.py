#!/usr/bin/env python3
"""Seal and verify unsigned candidate evidence; never publish or apply policy."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import tarfile
import zipfile

APP = 'SchoolOps-YouTube-Guard-Setup'
PLATFORMS = {'windows-2025': ('Windows', 'windows', '.zip'),
             'macos-15': ('Darwin', 'macos', '.tar.gz'),
             'ubuntu-24.04': ('Linux', 'linux', '.tar.gz')}
GUI_PASS = 'Tkinter GUI smoke passed:'
GUI_SAFE = 'No policy, Chrome extension or device restriction was installed.'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, obj):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(obj, sort_keys=True, indent=2) + '\n')


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def identity(commit, tree, run, attempt):
    for value in (commit, tree):
        require(re.fullmatch(r'[0-9a-f]{40}', value), 'invalid Git identity')
    for value in (run, attempt):
        require(re.fullmatch(r'[1-9][0-9]*', value), 'invalid Actions identity')
    return dict(sourceCommit=commit, sourceTree=tree, runId=run, runAttempt=attempt)


def payload(root):
    files = list(root.iterdir())
    require(all(p.is_file() and not p.is_symlink() for p in files), 'nonregular payload')
    return {p.name: digest(p) for p in sorted(files) if p.name != 'candidate.json'}


def validate(root, runner, expected, *, sealed):
    system, label, ext = PLATFORMS[runner]
    archive = APP + '-' + label + '-unsigned' + ext
    names = {archive, 'build-report.json', 'native-smoke.json', 'native-release-smoke.json',
             'SHA256SUMS.txt', 'START_HERE.txt', 'archive-smoke.json'}
    if system == 'Linux':
        names.add('source-gui-smoke.txt')
    files = payload(root)
    require(set(files) == names, 'missing or unexpected candidate payload')
    report = read(root / 'build-report.json')
    native = read(root / 'native-smoke.json')
    release = read(root / 'native-release-smoke.json')
    require(report.get('schema') == 1 and report.get('status') == 'unsigned_native_bundle_built', 'build status')
    require(report.get('sourceCommit') == expected['sourceCommit'], 'source commit mismatch')
    require(report.get('platform') == system and bool(report.get('architecture')), 'platform/architecture mismatch')
    require(report.get('python', '').startswith('3.12.') and report.get('pyinstaller') == '6.22.3', 'toolchain mismatch')
    require(report.get('archive') == archive and report.get('archiveSha256') == files[archive], 'archive mismatch')
    require((root / 'SHA256SUMS.txt').read_text().splitlines() == [files[archive] + '  ' + archive], 'checksum mismatch')
    require(native == report.get('nativeSmoke') and native.get('status') == 'passed' and native.get('frozen') is True, 'native smoke mismatch')
    require(release == report.get('nativeReleaseSmoke') and release.get('status') == 'passed', 'release smoke mismatch')
    require(release.get('commands') == {'key-id': 'passed', 'prepare': 'passed', 'sign': 'passed', 'missing-key': 'failed'}, 'release command evidence')
    require(all(release.get(key) is False for key in ('privateKeysRetained', 'policyApplied', 'remotePublication')), 'unsafe release evidence')
    require(read(root / 'archive-smoke.json') == native, 'extracted archive smoke mismatch')
    if system == 'Linux':
        log = (root / 'source-gui-smoke.txt').read_text(encoding='utf-8')
        require(GUI_PASS in log and GUI_SAFE in log, 'missing source GUI smoke evidence')
    record = dict(schema=1, status='unsigned_review_candidate', **expected, runner=runner,
                  architecture=report['architecture'], files=files,
                  sourceGuiSmoke='passed' if system == 'Linux' else 'not_run',
                  frozenArchiveSelfTest='passed', releaseCliSmoke='passed',
                  productionRelease=False, managedDeviceAcceptance=False)
    if sealed:
        require(read(root / 'candidate.json') == record, 'candidate manifest mismatch')
    return record


def archive_smoke(root, runner):
    system, label, ext = PLATFORMS[runner]
    archive = root / (APP + '-' + label + '-unsigned' + ext)
    require(digest(archive) == read(root / 'build-report.json').get('archiveSha256'), 'archive changed before replay')
    with tempfile.TemporaryDirectory(prefix='schoolops-extracted-') as tmp:
        work = Path(tmp)
        if system == 'Windows':
            with zipfile.ZipFile(archive) as z:
                for name in z.namelist():
                    path = Path(name)
                    require(not path.is_absolute() and not path.drive and '..' not in path.parts, 'unsafe ZIP member')
                z.extractall(work)
            exe = work / APP / (APP + '.exe')
        else:
            with tarfile.open(archive, 'r:gz') as t:
                t.extractall(work, filter='data')
            exe = (work / (APP + '.app') / 'Contents/MacOS' / APP if system == 'Darwin' else work / APP / APP)
        result = work / 'replayed.json'
        subprocess.run([str(exe), '--self-test', str(result)], cwd=work, check=True, timeout=120)
        report = read(result)
        require(report == read(root / 'native-smoke.json'), 'extracted archive self-test changed')
        write(root / 'archive-smoke.json', report)


def seal(root, runner, expected):
    require(git('rev-parse', 'HEAD') == expected['sourceCommit'], 'wrong checkout')
    require(git('rev-parse', 'HEAD^{tree}') == expected['sourceTree'], 'wrong tree')
    require(not git('status', '--porcelain', '--untracked-files=no'), 'tracked source modified')
    archive_smoke(root, runner)
    write(root / 'candidate.json', validate(root, runner, expected, sealed=False))


def index(root, expected, *, verify=False):
    require(root.is_dir() and not root.is_symlink(), 'invalid candidate set root')
    expected_names = set(PLATFORMS) | ({'INDEX.json'} if verify else set())
    require({p.name for p in root.iterdir()} == expected_names, 'incomplete or unexpected platform set')
    entries = {}
    for runner in sorted(PLATFORMS):
        folder = root / runner
        require(folder.is_dir() and not folder.is_symlink(), 'invalid platform directory')
        validate(folder, runner, expected, sealed=True)
        entries[runner] = digest(folder / 'candidate.json')
    result = dict(schema=1, **expected, status='unsigned_review_set', platformManifests=entries)
    if verify:
        manifest = root / 'INDEX.json'
        require(manifest.is_file() and not manifest.is_symlink(), 'invalid index file')
        require(read(manifest) == result, 'index mismatch')
    else:
        write(root / 'INDEX.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=['seal', 'index', 'verify'])
    p.add_argument('root', type=Path)
    p.add_argument('--runner', choices=PLATFORMS)
    for field in ('commit', 'tree', 'run', 'attempt'):
        p.add_argument('--' + field, required=True)
    a = p.parse_args()
    expected = identity(a.commit, a.tree, a.run, a.attempt)
    if a.operation == 'seal':
        require(a.runner is not None, 'runner required')
        seal(a.root.resolve(), a.runner, expected)
    else:
        index(a.root, expected, verify=a.operation == 'verify')
    print('Candidate evidence', a.operation, 'passed:', a.root)


if __name__ == '__main__':
    main()
