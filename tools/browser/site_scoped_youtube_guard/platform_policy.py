"""Apply a reviewed Chrome installation policy without replacing other entries.

The public application functions accept UTF-8 bytes (or text) containing exactly
one ``ExtensionSettings`` force-install entry. They return ``installed``,
``already_configured``, ``removed``, ``already_absent``, or ``not_owned``.
Application establishes local policy only, not Chrome installation/enforcement.

Linux writes a dedicated file and protected ownership receipt. Windows merges the
HKLM 64-bit ExtensionSettings value and records only entries this installer adds.
Removal requires that receipt and the unchanged entry. Rechecks reduce races;
Windows registry read/modify/write is not a cross-process transaction. macOS
output is an unsigned MDM handoff, never an enrollment or installation action.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import secrets
import stat
from urllib.parse import urlsplit
import uuid

try:
    import winreg
except ImportError:  # The module is also imported by Linux/macOS package builds.
    winreg = None


LINUX_MANAGED_PATH = Path("/etc/opt/chrome/policies/managed/school-ops-youtube-guard.json")
WINDOWS_POLICY_KEY = r"SOFTWARE\Policies\Google\Chrome"
WINDOWS_RECEIPT_KEY = r"SOFTWARE\SchoolOps\YouTubeGuard\PolicyReceipts"
WINDOWS_POLICY_VALUE = "ExtensionSettings"
_ID = re.compile(r"[a-p]{32}\Z")
_MAX_POLICY_BYTES = 4 * 1024 * 1024


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON policy key: {key}")
        value[key] = item
    return value


def _json(content):
    def reject_constant(value):
        raise ValueError(f"Non-JSON policy value: {value}")
    return json.loads(content, object_pairs_hook=_unique_object, parse_constant=reject_constant)


def _encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
            + "\n").encode("utf-8")


def _incoming(value):
    if not isinstance(value, dict) or len(value) != 1:
        raise ValueError("SchoolOps policy must contain exactly one extension ID")
    extension_id, settings = next(iter(value.items()))
    if not isinstance(extension_id, str) or not _ID.fullmatch(extension_id):
        raise ValueError("Invalid SchoolOps extension ID")
    if not isinstance(settings, dict) or set(settings) not in (
            {"installation_mode", "update_url"},
            {"installation_mode", "update_url", "override_update_url"}):
        raise ValueError("Unexpected SchoolOps extension policy fields")
    if settings["installation_mode"] != "force_installed":
        raise ValueError("SchoolOps policy must use force_installed")
    if "override_update_url" in settings and settings["override_update_url"] is not True:
        raise ValueError("override_update_url must be true when present")
    url = settings["update_url"]
    if not isinstance(url, str) or any(ord(char) < 33 for char in url):
        raise ValueError("Invalid extension update URL")
    parsed = urlsplit(url)
    # urlsplit defers malformed-port validation until this property is read.
    parsed.port
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
            parsed.password or parsed.fragment or parsed.query or not parsed.path or
            parsed.path == "/"):
        raise ValueError("An HTTPS extension update manifest URL is required")
    return extension_id, settings


def _document(content):
    if isinstance(content, str):
        content = content.encode("utf-8")
    if not isinstance(content, bytes) or len(content) > _MAX_POLICY_BYTES:
        raise ValueError("Policy must be a bounded UTF-8 JSON document")
    value = _json(content)
    if not isinstance(value, dict) or set(value) != {"ExtensionSettings"}:
        raise ValueError("Unexpected Chrome policy structure")
    _incoming(value["ExtensionSettings"])
    return content, value


def merge_extension_settings(existing, incoming):
    """Return a copy preserving wildcard/unrelated entries; refuse ID conflicts."""
    extension_id, settings = _incoming(incoming)
    if (not isinstance(existing, dict) or
            any(not isinstance(key, str) or not isinstance(value, dict)
                for key, value in existing.items())):
        raise ValueError("Existing ExtensionSettings must be a JSON dictionary")
    if extension_id in existing and existing[extension_id] != settings:
        raise ValueError("SchoolOps extension already has different policy; nothing changed")
    result = deepcopy(existing)
    result[extension_id] = deepcopy(settings)
    return result


def _assert_root_controlled(info, directory=False):
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected_type(info.st_mode):
        raise PermissionError("Chrome policy paths must be regular files and directories")
    if info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise PermissionError("Every Chrome policy ancestor and file must be root-controlled")


def _linux_guard(target):
    if platform.system() != "Linux":
        raise RuntimeError("Linux policy application requires Linux")
    if os.geteuid() != 0:
        raise PermissionError("Run the reviewed policy action as root")
    target = Path(target)
    if target != LINUX_MANAGED_PATH or not target.is_absolute():
        raise ValueError("Refusing a noncanonical Chrome policy path")
    return target


def _policy_directory(target, create):
    """Hold directory descriptors throughout traversal; never follow a symlink."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    current = os.open("/", flags)
    try:
        _assert_root_controlled(os.fstat(current), directory=True)
        for part in target.parent.parts[1:]:
            try:
                child = os.open(part, flags, dir_fd=current)
            except FileNotFoundError:
                if not create:
                    os.close(current)
                    return None
                try:
                    os.mkdir(part, mode=0o755, dir_fd=current)
                except FileExistsError:
                    pass
                child = os.open(part, flags, dir_fd=current)
            os.close(current)
            current = child
            _assert_root_controlled(os.fstat(current), directory=True)
        return current
    except BaseException:
        os.close(current)
        raise


def _read_at(directory, name):
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=directory)
    except FileNotFoundError:
        return None
    with os.fdopen(descriptor, "rb") as source:
        _assert_root_controlled(os.fstat(source.fileno()))
        content = source.read(_MAX_POLICY_BYTES + 1)
    if len(content) > _MAX_POLICY_BYTES:
        raise ValueError(f"Policy file is too large: {name}")
    return content


def _other_linux_policies(directory, own_name):
    for name in os.listdir(directory):
        if name == own_name or not name.endswith(".json"):
            continue
        content = _read_at(directory, name)
        if content is None:
            raise ValueError(f"Chrome policy changed during inspection: {name}")
        try:
            value = _json(content)
        except (ValueError, UnicodeError) as exc:
            raise ValueError(f"Cannot inspect malformed Chrome policy: {name}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"Chrome policy must be an object: {name}")
        if "ExtensionSettings" in value:
            raise ValueError(
                f"Existing ExtensionSettings in {name}; merge through its administrator "
                "instead of adding a competing policy file")


def _exclusive_file(directory, name, content):
    """Publish complete fsynced bytes without replacing a pre-existing name."""
    temporary = ".schoolops-policy-" + secrets.token_hex(16)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o644, dir_fd=directory)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, name, src_dir_fd=directory, dst_dir_fd=directory,
                follow_symlinks=False)
        os.fsync(directory)
    finally:
        os.unlink(temporary, dir_fd=directory)


def _linux_receipt_name(target):
    # Chrome consumes *.json in this directory, so bookkeeping uses .receipt.
    return target.stem + ".receipt"


def _receipt(content):
    return _encode({"schema": 1, "policySha256": hashlib.sha256(content).hexdigest()})


def apply_linux_policy_content(content, target=None):
    """Install a dedicated policy, refusing competing dictionaries or changed files."""
    content, _ = _document(content)
    target = _linux_guard(LINUX_MANAGED_PATH if target is None else target)
    directory = _policy_directory(target, create=True)
    try:
        _other_linux_policies(directory, target.name)
        existing = _read_at(directory, target.name)
        receipt_name = _linux_receipt_name(target)
        receipt = _read_at(directory, receipt_name)
        if existing is not None:
            if existing != content:
                raise ValueError("Existing SchoolOps policy differs; nothing changed")
            if receipt is not None and receipt != _receipt(content):
                raise ValueError("SchoolOps ownership receipt differs; nothing changed")
            # Do not claim ownership of an administrator's identical pre-existing file.
            return "already_configured"
        if receipt is not None:
            raise ValueError("An orphaned SchoolOps receipt exists; review it before installing")
        _other_linux_policies(directory, target.name)
        _exclusive_file(directory, target.name, content)
        try:
            _exclusive_file(directory, receipt_name, _receipt(content))
        except BaseException:
            # Best-effort rollback of this installation, never overwrite a new policy.
            if _read_at(directory, target.name) == content:
                os.unlink(target.name, dir_fd=directory)
                os.fsync(directory)
            raise
        return "installed"
    finally:
        os.close(directory)


def remove_linux_policy_content(content, target=None):
    """Remove only an unchanged policy with the receipt created by this installer."""
    content, _ = _document(content)
    target = _linux_guard(LINUX_MANAGED_PATH if target is None else target)
    directory = _policy_directory(target, create=False)
    if directory is None:
        return "already_absent"
    try:
        existing = _read_at(directory, target.name)
        receipt_name = _linux_receipt_name(target)
        receipt = _read_at(directory, receipt_name)
        if receipt is None:
            return "already_absent" if existing is None else "not_owned"
        if receipt != _receipt(content):
            raise ValueError("SchoolOps ownership receipt differs; nothing removed")
        if existing is not None and existing != content:
            raise ValueError("SchoolOps policy was changed; nothing removed")
        if existing is not None:
            if _read_at(directory, target.name) != content:
                raise ValueError("SchoolOps policy changed during removal")
            os.unlink(target.name, dir_fd=directory)
        if _read_at(directory, receipt_name) != receipt:
            raise ValueError("SchoolOps receipt changed during removal")
        os.unlink(receipt_name, dir_fd=directory)
        os.fsync(directory)
        return "removed" if existing is not None else "already_absent"
    finally:
        os.close(directory)


def _windows_admin():
    import ctypes
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def _windows_guard():
    if platform.system() != "Windows" or winreg is None:
        raise RuntimeError("Windows policy application requires Windows")
    if not _windows_admin():
        raise PermissionError("Run the reviewed policy action as administrator")


def _win_read(path, name):
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            value, kind = winreg.QueryValueEx(key, name)
    except FileNotFoundError:
        return None
    if kind != winreg.REG_SZ or not isinstance(value, str):
        raise ValueError(f"Expected REG_SZ policy value: {name}")
    return value


def _win_write(path, name, value):
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0,
                           winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)


def _win_delete(path, name):
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0,
                            winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as key:
            winreg.DeleteValue(key, name)
    except FileNotFoundError:
        pass


def _windows_receipt(extension_id, settings):
    return _encode({"schema": 1, "extensionId": extension_id,
                    "settings": settings}).decode("utf-8")


def _windows_snapshot():
    raw = _win_read(WINDOWS_POLICY_KEY, WINDOWS_POLICY_VALUE)
    value = {} if raw is None else _json(raw)
    if not isinstance(value, dict):
        raise ValueError("Existing ExtensionSettings must be a dictionary")
    return raw, value


def _windows_compare_write(previous, updated):
    if _win_read(WINDOWS_POLICY_KEY, WINDOWS_POLICY_VALUE) != previous:
        raise ValueError("Chrome policy changed during installation; retry after reviewing it")
    if updated:
        _win_write(WINDOWS_POLICY_KEY, WINDOWS_POLICY_VALUE, _encode(updated).decode("utf-8"))
    else:
        _win_delete(WINDOWS_POLICY_KEY, WINDOWS_POLICY_VALUE)


def apply_windows_policy_content(content):
    """Merge one force-install entry in HKLM's 64-bit policy view, with ownership."""
    _, policy = _document(content)
    _windows_guard()
    incoming = policy["ExtensionSettings"]
    extension_id, settings = _incoming(incoming)
    previous, existing = _windows_snapshot()
    updated = merge_extension_settings(existing, incoming)
    receipt = _win_read(WINDOWS_RECEIPT_KEY, extension_id)
    expected = _windows_receipt(extension_id, settings)
    if receipt is not None and receipt != expected:
        raise ValueError("SchoolOps ownership receipt differs; nothing changed")
    if extension_id in existing:
        return "already_configured"
    if receipt is not None:
        raise ValueError("An orphaned SchoolOps receipt exists; review it before installing")
    _windows_compare_write(previous, updated)
    try:
        if _win_read(WINDOWS_RECEIPT_KEY, extension_id) is not None:
            raise ValueError("SchoolOps receipt appeared during installation")
        _win_write(WINDOWS_RECEIPT_KEY, extension_id, expected)
    except BaseException:
        # Restore the prior policy only if nobody has changed the merged value.
        merged = _encode(updated).decode("utf-8")
        if _win_read(WINDOWS_POLICY_KEY, WINDOWS_POLICY_VALUE) == merged:
            if previous is None:
                _win_delete(WINDOWS_POLICY_KEY, WINDOWS_POLICY_VALUE)
            else:
                _win_write(WINDOWS_POLICY_KEY, WINDOWS_POLICY_VALUE, previous)
        raise
    return "installed"


def remove_windows_policy_content(content):
    """Remove only our unchanged, receipted ID; retain current unrelated entries."""
    _, policy = _document(content)
    _windows_guard()
    extension_id, settings = _incoming(policy["ExtensionSettings"])
    previous, existing = _windows_snapshot()
    receipt = _win_read(WINDOWS_RECEIPT_KEY, extension_id)
    if receipt is None:
        return "already_absent" if extension_id not in existing else "not_owned"
    if receipt != _windows_receipt(extension_id, settings):
        raise ValueError("SchoolOps ownership receipt differs; nothing removed")
    if extension_id not in existing:
        _win_delete(WINDOWS_RECEIPT_KEY, extension_id)
        return "already_absent"
    if existing[extension_id] != settings:
        raise ValueError("SchoolOps policy was changed; nothing removed")
    updated = deepcopy(existing)
    del updated[extension_id]
    if _win_read(WINDOWS_RECEIPT_KEY, extension_id) != receipt:
        raise ValueError("SchoolOps receipt changed during removal")
    _windows_compare_write(previous, updated)
    _win_delete(WINDOWS_RECEIPT_KEY, extension_id)
    return "removed"


def macos_profile(content):
    """Return an unsigned .mobileconfig MDM handoff with stable payload identities."""
    _, policy = _document(content)
    extension_id, _ = _incoming(policy["ExtensionSettings"])
    identifier = "org.schoolops.youtube-guard." + extension_id
    def identity(suffix):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, identifier + suffix)).upper()
    profile = {
        "PayloadType": "Configuration",
        "PayloadVersion": 1,
        "PayloadIdentifier": identifier,
        "PayloadUUID": identity(".profile"),
        "PayloadDisplayName": "SchoolOps YouTube Guard",
        "PayloadOrganization": "SchoolOps",
        "PayloadScope": "System",
        "PayloadContent": [{
            "PayloadType": "com.apple.ManagedClient.preferences",
            "PayloadVersion": 1,
            "PayloadIdentifier": identifier + ".chrome",
            "PayloadUUID": identity(".chrome"),
            "PayloadEnabled": True,
            "PayloadContent": {
                "com.google.Chrome": {"Forced": [{"mcx_preference_settings": policy}]},
            },
        }],
    }
    return plistlib.dumps(profile, fmt=plistlib.FMT_XML, sort_keys=True)
