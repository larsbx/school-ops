#!/usr/bin/env python3
"""Prepare, sign, stage and independently check a self-hosted SchoolOps release.

All uploads are outside this module. Staging writes only a separately selected
local web-root, after approval of its exact plan. Verification performs anonymous
read-only HTTPS requests. Neither operation applies policy or enrolls a device.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import sys
import tempfile
import time
from urllib import error, request
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
import zipfile

import crx3
import installer_core as core


SCHEMA = 1
XML_NS = "http://www.google.com/update2/response"
GUARDS = ("identity_ok", "version_ok", "zip_ok", "crx_ok", "signature_ok",
          "tls_ok", "manifest_ok", "download_ok")
HEX = re.compile(r"[0-9a-f]{64}\Z")
MAX_MANIFEST_BYTES = 64 * 1024
PLAN_KEYS = {"schema", "kind", "extension_id", "extension_version", "extension_zip_sha256",
             "public_key_sha256", "update_url", "crx_url", "previous", "release_id"}


def _json(value):
    return core.pretty_json(value).encode("utf-8")


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def publication_admitted(guards):
    """Finite guard projection replayed against Lean/Quint; not a trust boundary.

    Only verify_publication computes these observations. A caller-supplied dict
    does not establish TLS, signature verification, or remote publication.
    """
    return (isinstance(guards, dict) and set(guards) == set(GUARDS)
            and all(guards[name] is True for name in GUARDS))


def public_key_id(path):
    return crx3.extension_id(crx3.public_key_bytes(path))


def _version(value):
    core.validate_version(value)
    parts = [int(part) for part in value.split(".")]
    return tuple(parts + [0] * (4 - len(parts)))


def _url(value):
    if not isinstance(value, str) or not value.isascii():
        raise ValueError("Release endpoints must be explicit ASCII HTTPS URLs")
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid HTTPS port") from exc
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or any(ord(c) < 33 for c in value) or "\\" in value
            or not re.fullmatch(r"/[A-Za-z0-9._/-]+", parsed.path)
            or any(part in ("", ".", "..") for part in parsed.path.split("/")[1:])
            or parsed.path.endswith("/") or port == 0):
        raise ValueError("Use a complete HTTPS file URL without credentials, query, fragment or traversal")
    return parsed


def _endpoints(update_url, crx_url):
    update, package = _url(update_url), _url(crx_url)
    if (update.hostname, update.port or 443) != (package.hostname, package.port or 443):
        raise ValueError("Update manifest and CRX must use the same approved HTTPS origin")
    if not update.path.endswith(".xml") or not package.path.endswith(".crx"):
        raise ValueError("Use an .xml update manifest and an immutable .crx package path")
    return update, package


def _root(value):
    path = Path(value).expanduser().absolute()
    if path.name == "release.json":
        path = path.parent
    if path.is_symlink() or not path.is_dir():
        raise ValueError("Release must be a regular local directory")
    return path


def _read(path, limit=crx3.MAX_CRX_BYTES):
    return crx3.read_file(path, limit)


def _archive_settings(archive):
    """Recompile configuration and compare the complete original canonical ZIP."""
    if len(archive) > crx3.MAX_ZIP_BYTES:
        raise ValueError("Prepared ZIP exceeds the supported size limit")
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            if sorted(zf.namelist()) != ["config.json", "manifest.json", "rules.json"]:
                raise ValueError("Prepared ZIP has missing, extra or duplicate entries")
            if any(i.file_size > crx3.MAX_ZIP_BYTES or i.compress_type != zipfile.ZIP_STORED
                   or i.flag_bits & 1 for i in zf.infolist()):
                raise ValueError("Only the wizard's bounded stored ZIP is supported")
            cfg = core.read_json(zf.read("config.json"))
            manifest = core.read_json(zf.read("manifest.json"))
            checked = core.validate_settings({**cfg, "channel": "self_hosted", "update_url": "",
                                              "extension_version": manifest.get("version")})
    except (zipfile.BadZipFile, KeyError, TypeError) as exc:
        raise ValueError("Invalid prepared extension ZIP") from exc
    if archive != core.extension_zip(core.extension_files(checked)):
        raise ValueError("ZIP fingerprint differs from the wizard's exact compiled configuration")
    return checked


def _plan_id(plan):
    return _hash(_json({key: value for key, value in plan.items() if key != "release_id"}))


def _validate_plan(plan, archive, public):
    if not isinstance(plan, dict) or set(plan) != PLAN_KEYS:
        raise ValueError("Unexpected release contract fields")
    if plan["schema"] != SCHEMA or plan["kind"] != "schoolops-self-hosted-crx3":
        raise ValueError("Unsupported release contract")
    checked = _archive_settings(archive)
    if (plan["release_id"] != _plan_id(plan) or plan["extension_zip_sha256"] != _hash(archive)
            or plan["public_key_sha256"] != _hash(public)):
        raise ValueError("Release fingerprint differs from the prepared contract")
    if plan["extension_version"] != checked["extension_version"]:
        raise ValueError("Unauthorized version change from the prepared extension")
    if plan["extension_id"] != crx3.extension_id(public):
        raise ValueError("Release extension ID differs from the pinned signing key")
    _endpoints(plan["update_url"], plan["crx_url"])
    previous = plan["previous"]
    if previous is not None:
        required = {"release_id", "extension_id", "extension_version", "update_url", "crx_url",
                    "manifest_sha256", "crx_sha256"}
        if not isinstance(previous, dict) or set(previous) != required:
            raise ValueError("Invalid predecessor release binding")
        if any(not isinstance(previous[key], str) or not HEX.fullmatch(previous[key])
               for key in ("release_id", "manifest_sha256", "crx_sha256")):
            raise ValueError("Invalid predecessor fingerprint")
        if previous["extension_id"] != plan["extension_id"] or previous["update_url"] != plan["update_url"]:
            raise ValueError("Updates must preserve the previous identity and update endpoint")
        if _version(plan["extension_version"]) <= _version(previous["extension_version"]):
            raise ValueError("Version must strictly increase; equal numeric aliases and downgrades are refused")
        _endpoints(previous["update_url"], previous["crx_url"])
        if previous["crx_url"] == plan["crx_url"]:
            raise ValueError("New versions require a new immutable CRX URL")
    return checked


def _load(release):
    root = _root(release)
    raw = _read(root / "release.json", MAX_MANIFEST_BYTES)
    plan = core.read_json(raw)
    if raw != _json(plan):
        raise ValueError("Release contract must use canonical JSON")
    archive = _read(root / "extension.zip", crx3.MAX_ZIP_BYTES)
    public = _read(root / "public-key.der", 2048)
    _validate_plan(plan, archive, public)
    if _read(root / "signing-input.bin") != crx3.signing_input(archive, public):
        raise ValueError("Signing input differs from the immutable release contract")
    return root, plan, archive, public


def load_release(release):
    return _load(release)[1]


def _new_directory(destination, files):
    destination = Path(destination).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Refusing to replace an existing release directory")
    if not destination.parent.is_dir():
        raise ValueError("Create the release parent directory first")
    temp = Path(tempfile.mkdtemp(prefix=".schoolops-release-", dir=destination.parent))
    try:
        for relative, data in files.items():
            (temp / relative).write_bytes(data)
        destination.mkdir()
        try:
            for child in temp.iterdir():
                child.rename(destination / child.name)
        except BaseException:
            shutil.rmtree(destination)
            raise
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return destination


def prepare_release(bundle, destination, *, public_key, expected_id, expected_version,
                    update_url, crx_url, previous_release=None, initial_release=False):
    """Freeze an explicitly authorized ID/version and the wizard's exact ZIP."""
    root, settings = core.load_bundle(bundle)
    if settings["channel"] != "self_hosted":
        raise ValueError("Prepare a self-hosted setup; the Chrome Web Store flow remains separate")
    public = crx3.public_key_bytes(public_key)
    if not isinstance(expected_id, str) or expected_id != crx3.extension_id(public):
        raise ValueError("Expected extension ID does not match the public signing key")
    if expected_version != settings["extension_version"]:
        raise ValueError("Unauthorized version change: expected version must equal the frozen setup")
    if settings["extension_id"] and settings["extension_id"] != expected_id:
        raise ValueError("Prepared setup was bound to a different extension ID")
    if bool(previous_release) == bool(initial_release):
        raise ValueError("Supply a previous signed release or explicitly select initial release")
    previous = None
    if previous_release:
        _, prior, _old_archive, _old_public, signed, _crx, _xml = _signed(previous_release)
        previous = {key: prior[key] for key in
                    ("release_id", "extension_id", "extension_version", "update_url", "crx_url")}
        previous.update({key: signed[key] for key in ("manifest_sha256", "crx_sha256")})
    archive = _read(root / "extension.zip", crx3.MAX_ZIP_BYTES)
    plan = {"schema": SCHEMA, "kind": "schoolops-self-hosted-crx3",
            "extension_id": expected_id, "extension_version": expected_version,
            "extension_zip_sha256": _hash(archive), "public_key_sha256": _hash(public),
            "update_url": update_url, "crx_url": crx_url, "previous": previous}
    plan["release_id"] = _plan_id(plan)
    _validate_plan(plan, archive, public)
    return _new_directory(destination, {"release.json": _json(plan), "extension.zip": archive,
                                       "public-key.der": public,
                                       "signing-input.bin": crx3.signing_input(archive, public)})


def update_manifest(plan, crx):
    # URL validation excludes XML metacharacters; ElementTree still escapes attrs.
    root = ET.Element("gupdate", {"xmlns": XML_NS, "protocol": "2.0"})
    app = ET.SubElement(root, "app", {"appid": plan["extension_id"]})
    ET.SubElement(app, "updatecheck", {"codebase": plan["crx_url"],
                                     "version": plan["extension_version"],
                                     "hash_sha256": _hash(crx), "size": str(len(crx))})
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8") + b"\n"


def _signed_metadata(plan, crx, xml):
    return {"schema": SCHEMA, "release_id": plan["release_id"], "crx_sha256": _hash(crx),
            "manifest_sha256": _hash(xml), "crx_size": len(crx)}


def _fsync_dir(path):
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _atomic_file(path, data, *, immutable):
    """Durable replacement or exclusive atomic insertion, never partial bytes."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Refusing a symlink publication target")
    if immutable and path.exists():
        if _read(path) != data:
            raise ValueError("Immutable publication path contains different bytes")
        return
    fd, temporary = tempfile.mkstemp(prefix=".schoolops-part-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if immutable:
            try:
                os.link(temporary, path)
            except FileExistsError:
                if _read(path) != data:
                    raise ValueError("Immutable publication path contains different bytes")
        else:
            os.replace(temporary, path)
        _fsync_dir(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def _lock(directory):
    """Cooperating publishers serialize; OS releases the lock after a crash."""
    path = Path(directory) / ".schoolops-release.lock"
    if path.is_symlink():
        raise ValueError("Refusing a symlink publication lock")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    locked = False
    try:
        try:
            if os.name == "nt":
                import msvcrt
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"0")
                    os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, PermissionError) as exc:
            raise ValueError("Another publisher holds this directory's release lock") from exc
        locked = True
        yield
    finally:
        if locked:
            if os.name == "nt":
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def assemble_release(release, signature):
    root, plan, archive, public = _load(release)
    signature = _read(signature, 1024) if not isinstance(signature, bytes) else signature
    crx = crx3.assemble(archive, public, signature)
    crx3.verify(crx, expected_zip=archive, expected_key=public, expected_id=plan["extension_id"])
    xml = update_manifest(plan, crx)
    with _lock(root):
        _atomic_file(root / "extension.crx", crx, immutable=True)
        _atomic_file(root / "update.xml", xml, immutable=True)
        # This commit marker is written last; retry validates every existing byte.
        _atomic_file(root / "signed.json", _json(_signed_metadata(plan, crx, xml)), immutable=True)
    return root


def sign_release(release, key):
    root, _plan, archive, public = _load(release)
    signature = crx3.sign_payload(crx3.signing_input(archive, public), key)
    return assemble_release(root, signature)


def _signed(release):
    root, plan, archive, public = _load(release)
    crx, xml = _read(root / "extension.crx"), _read(root / "update.xml", MAX_MANIFEST_BYTES)
    crx3.verify(crx, expected_zip=archive, expected_key=public, expected_id=plan["extension_id"])
    if xml != update_manifest(plan, crx):
        raise ValueError("Signed update manifest differs from the pinned ID/version/package")
    metadata = _signed_metadata(plan, crx, xml)
    if _read(root / "signed.json", MAX_MANIFEST_BYTES) != _json(metadata):
        raise ValueError("Missing or inconsistent signed-release commit record")
    return root, plan, archive, public, metadata, crx, xml


def _web_path(web_root, url, *, create=False):
    root = Path(web_root).expanduser().absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Select an existing local staging web-root directory")
    path = root
    parts = _url(url).path.split("/")[1:]
    for index, part in enumerate(parts):
        path = path / part
        if path.is_symlink():
            raise ValueError("Publication paths must not contain symlinks")
        if index < len(parts) - 1:
            if create:
                path.mkdir(exist_ok=True)
            if path.exists() and not path.is_dir():
                raise ValueError("Publication parent is not a directory")
    return path


def _publication_plan(snapshot, web_root):
    """Build the review plan from one fully verified, immutable byte snapshot."""
    _root_, plan, _archive, _public, signed, crx, xml = snapshot
    package = _web_path(web_root, plan["crx_url"])
    manifest = _web_path(web_root, plan["update_url"])
    existing_package = _hash(_read(package)) if package.exists() else None
    existing_manifest = _hash(_read(manifest, MAX_MANIFEST_BYTES)) if manifest.exists() else None
    predecessor = plan["previous"]["manifest_sha256"] if plan["previous"] else None
    if existing_package not in (None, signed["crx_sha256"]):
        raise ValueError("Immutable CRX URL already contains conflicting package bytes")
    if existing_manifest not in (predecessor, signed["manifest_sha256"]):
        raise ValueError("Manifest does not match the authorized predecessor; refusing overwrite/downgrade")
    actions = {"schema": SCHEMA, "release_id": plan["release_id"],
               "web_root": str(Path(web_root).expanduser().absolute()),
               "expected_manifest_sha256": existing_manifest,
               "writes": [{"order": 1, "path": str(package), "url": plan["crx_url"],
                           "sha256": _hash(crx), "size": len(crx), "mode": "immutable"},
                          {"order": 2, "path": str(manifest), "url": plan["update_url"],
                           "sha256": _hash(xml), "size": len(xml), "mode": "atomic_replace"}],
               "network_upload": False, "policy_change": False}
    actions["approval_sha256"] = _hash(_json(actions))
    return actions


def publication_plan(release, web_root):
    """Show exact local writes and predecessor before asking for approval."""
    return _publication_plan(_signed(release), web_root)


def stage_release(release, web_root, *, approve_plan_sha256):
    """Apply only the reviewed local plan; never upload or change enterprise policy."""
    root = Path(web_root).expanduser().absolute()
    # Validate before creating even the lock file.
    snapshot = _signed(release)
    plan_before = _publication_plan(snapshot, root)
    if approve_plan_sha256 != plan_before["approval_sha256"]:
        raise ValueError("Review plan-stage output and approve that exact plan SHA-256")
    with _lock(root):
        approved = _publication_plan(snapshot, root)
        if approve_plan_sha256 != approved["approval_sha256"]:
            raise ValueError("Publication changed after review; inspect and approve a new plan")
        _, plan, _archive, _public, _signed_, crx, xml = snapshot
        package = _web_path(root, plan["crx_url"], create=True)
        manifest = _web_path(root, plan["update_url"], create=True)
        _atomic_file(package, crx, immutable=True)
        # Recheck the predecessor immediately before committing the manifest.
        actual = _hash(_read(manifest, MAX_MANIFEST_BYTES)) if manifest.exists() else None
        if actual != approved["expected_manifest_sha256"]:
            raise ValueError("Manifest changed during staging; new package remains inactive")
        if actual != _hash(xml):
            _atomic_file(manifest, xml, immutable=False)
    return {"release_id": plan["release_id"], "staged": True, "remote_verified": False,
            "policy_applied": False, "managed_device_enforcement": False}


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Release downloads must not redirect from the pinned HTTPS URLs")


def _https_get(url, *, ca_file, limit, expected_types):
    _url(url)
    context = ssl.create_default_context(cafile=str(ca_file) if ca_file else None)
    # No cookie jar, credential handler, client certificate, browser session, or
    # proxy configuration inherited from the operator's environment.
    opener = request.build_opener(request.ProxyHandler({}), _NoRedirect(),
                                 request.HTTPSHandler(context=context))
    req = request.Request(url, headers={"User-Agent": "SchoolOps-Release-Check/1",
                                      "Accept-Encoding": "identity", "Cache-Control": "no-cache"})
    started = time.monotonic()
    try:
        with opener.open(req, timeout=10) as response:
            if response.status != 200 or response.geturl() != url:
                raise ValueError("Publication download did not return the exact pinned URL with status 200")
            if response.headers.get_content_type() not in expected_types:
                raise ValueError("Publication endpoint serves an unsupported Content-Type")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("Release downloads must serve unencoded exact bytes")
            length = response.headers.get("Content-Length")
            if length is not None and (not length.isdecimal() or int(length) > limit):
                raise ValueError("Publication download exceeds the supported size limit")
            chunks, total = [], 0
            while True:
                chunk = response.read1(min(65536, limit + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > limit or time.monotonic() - started > 30:
                    raise ValueError("Publication download exceeds its size/time limit")
            data = b"".join(chunks)
            if length is not None and int(length) != len(data):
                raise ValueError("Publication download was interrupted or truncated")
            return data
    except (error.URLError, OSError, TimeoutError) as exc:
        raise ValueError("HTTPS publication download failed (TLS, HTTP status, connection or timeout)") from exc


def _check_manifest(xml, plan, signed):
    try:
        text = xml.decode("utf-8", "strict")
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ValueError("Update manifests cannot contain DTDs or entities")
        root = ET.fromstring(text)
    except (UnicodeError, ET.ParseError) as exc:
        raise ValueError("Publication endpoint did not serve valid UTF-8 update XML") from exc
    if root.tag != f"{{{XML_NS}}}gupdate" or root.attrib != {"protocol": "2.0"} or len(root) != 1:
        raise ValueError("Unexpected update-manifest namespace, protocol or app count")
    app = root[0]
    if app.tag != f"{{{XML_NS}}}app" or app.attrib != {"appid": plan["extension_id"]} or len(app) != 1:
        raise ValueError("Update manifest extension ID differs from the pinned release")
    update = app[0]
    if update.tag != f"{{{XML_NS}}}updatecheck" or len(update):
        raise ValueError("Missing or unexpected updatecheck element")
    if update.get("version") != plan["extension_version"]:
        raise ValueError("Unauthorized version change in published update manifest")
    expected = {"codebase": plan["crx_url"], "version": plan["extension_version"],
                "hash_sha256": signed["crx_sha256"], "size": str(signed["crx_size"])}
    if update.attrib != expected:
        raise ValueError("Update manifest package URL/fingerprint differs from the prepared release")


def verify_publication(release, *, ca_file=None):
    """Fresh, anonymous TLS downloads compared against independently pinned bytes."""
    _, plan, archive, public, signed, crx, expected_xml = _signed(release)
    xml = _https_get(plan["update_url"], ca_file=ca_file, limit=MAX_MANIFEST_BYTES,
                     expected_types={"application/xml", "text/xml"})
    _check_manifest(xml, plan, signed)
    if xml != expected_xml:
        raise ValueError("Published manifest bytes differ from the prepared release")
    downloaded = _https_get(plan["crx_url"], ca_file=ca_file, limit=crx3.MAX_CRX_BYTES,
                            expected_types={"application/x-chrome-extension"})
    if downloaded != crx:
        raise ValueError("Published package fingerprint differs from the prepared signed CRX")
    checked = crx3.verify(downloaded, expected_zip=archive, expected_key=public,
                         expected_id=plan["extension_id"])
    # Recheck after the CRX transfer and refuse detected manifest changes. Two
    # matching observations cannot exclude an intervening change-and-change-back
    # or guarantee what the server will return after this check.
    again = _https_get(plan["update_url"], ca_file=ca_file, limit=MAX_MANIFEST_BYTES,
                       expected_types={"application/xml", "text/xml"})
    if again != xml:
        raise ValueError("Update manifest changed during publication verification; retry")
    guards = {"identity_ok": checked["extension_id"] == plan["extension_id"],
              "version_ok": _archive_settings(archive)["extension_version"] == plan["extension_version"],
              "zip_ok": checked["extension_zip_sha256"] == plan["extension_zip_sha256"],
              "crx_ok": checked["crx_sha256"] == signed["crx_sha256"],
              "signature_ok": True, "tls_ok": True, "manifest_ok": again == expected_xml,
              "download_ok": downloaded == crx}
    if not publication_admitted(guards):
        raise ValueError("Release verification guards did not all pass")
    return {"schema": SCHEMA, "scope": "downloaded_release_bytes",
            **{key: plan[key] for key in ("release_id", "extension_id", "extension_version",
                                          "extension_zip_sha256", "update_url", "crx_url",
                                          "public_key_sha256")},
            "crx_sha256": signed["crx_sha256"], "manifest_sha256": signed["manifest_sha256"],
            "observed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "managed_device_enforcement": False, "policy_applied": False, "verification": guards}


def export_verified_deployment(bundle, release, destination, *, ca_file=None, target_os=None):
    root, settings = core.load_bundle(bundle)
    plan = load_release(release)
    if settings["channel"] != "self_hosted" or _read(root / "extension.zip") != _load(release)[2]:
        raise ValueError("Release fingerprint differs from this prepared self-hosted configuration")
    if target_os is not None:
        settings["target_os"] = target_os
        core.validate_settings(settings)
    receipt = verify_publication(release, ca_file=ca_file)
    settings.update(extension_id=plan["extension_id"], update_url=plan["update_url"],
                    publication_confirmed=True, published_extension_sha256=plan["extension_zip_sha256"],
                    publication_receipt=receipt)
    return core.export_bundle(settings, destination)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", help="Write a local JSON operation report (required by windowed native apps)")
    commands = parser.add_subparsers(dest="command", required=True)
    identify = commands.add_parser("key-id", help="Derive extension ID from a PUBLIC key")
    identify.add_argument("public_key")
    prepare = commands.add_parser("prepare", help="Freeze a deterministic signing contract")
    prepare.add_argument("bundle")
    prepare.add_argument("destination")
    for option in ("public-key", "expected-id", "expected-version", "update-url", "crx-url"):
        prepare.add_argument("--" + option, required=True)
    baseline = prepare.add_mutually_exclusive_group(required=True)
    baseline.add_argument("--previous-release")
    baseline.add_argument("--initial-release", action="store_true")
    sign = commands.add_parser("sign", help="Sign locally using OpenSSL; never upload a key")
    sign.add_argument("release")
    sign.add_argument("--key", required=True)
    assemble = commands.add_parser("assemble", help="Verify and import an external RSA signature")
    assemble.add_argument("release")
    assemble.add_argument("--signature", required=True)
    for name in ("plan-stage", "stage"):
        sub = commands.add_parser(name, help="Review/apply package-first, manifest-last LOCAL staging")
        sub.add_argument("release")
        sub.add_argument("web_root")
        if name == "stage":
            sub.add_argument("--approve-plan-sha256", required=True)
    verify = commands.add_parser("verify", help="Download and verify exact bytes over HTTPS")
    verify.add_argument("release")
    verify.add_argument("--ca-file", help="Explicit CA bundle (normal TLS hostname verification remains enabled)")
    deploy = commands.add_parser("export-deployment", help="Fresh HTTPS verification then wizard bundle export")
    deploy.add_argument("bundle")
    deploy.add_argument("release")
    deploy.add_argument("destination")
    deploy.add_argument("--ca-file")
    deploy.add_argument("--target-os", choices=("linux", "windows", "macos", "chromeos"))
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    report_path = args.pop("report")
    if sys.stdout is None and not report_path:
        raise ValueError("A windowed native release command requires --report FILE before the command")
    report_ready = False

    def report(status, **detail):
        value = {"schema": 1, "scope": "schoolops_release_operation", "status": status,
                 "command": command, "recorded_at_utc": datetime.now(timezone.utc).isoformat(), **detail}
        if report_path:
            target = Path(report_path).expanduser().absolute()
            _atomic_file(target, _json(value), immutable=False)
        return value

    try:
        if report_path:
            target = Path(report_path).expanduser().absolute()
            if target.is_symlink() or not target.parent.is_dir():
                raise ValueError("Operation report requires an existing parent and a regular file path")
            for key in ("release", "bundle", "destination", "web_root"):
                if key in args and args[key]:
                    source = Path(args[key]).expanduser().absolute()
                    if source.name in ("release.json", "setup.json"):
                        source = source.parent
                    actual_target, actual_source = target.resolve(), source.resolve()
                    if actual_target == actual_source or actual_source in actual_target.parents:
                        raise ValueError("Write the operation report outside release, setup and staging directories")
            if target.exists():
                previous_report = core.read_json(_read(target, MAX_MANIFEST_BYTES))
                if (not isinstance(previous_report, dict) or previous_report.get("schema") != 1
                        or previous_report.get("scope") != "schoolops_release_operation"):
                    raise ValueError("Refusing to overwrite a file that is not a release operation report")
        report_ready = True
        report("running")
        if command == "key-id":
            result = public_key_id(args["public_key"])
        elif command == "prepare":
            result = str(prepare_release(**args))
        elif command == "sign":
            result = str(sign_release(**args))
        elif command == "assemble":
            result = str(assemble_release(**args))
        elif command == "plan-stage":
            result = publication_plan(**args)
        elif command == "stage":
            result = stage_release(**args)
        elif command == "verify":
            result = verify_publication(**args)
        else:
            result = str(export_verified_deployment(**args))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Only replace the report after its path passed preflight; an invalid
        # output path must never overwrite the file it was intended to protect.
        if report_ready:
            report("failed", error=str(exc))
        parser.exit(1, f"Release refused: {exc}\n")
    report("passed", result=result)
    if sys.stdout is not None:
        print(core.pretty_json(result) if isinstance(result, dict) else result)


if __name__ == "__main__":
    main()
