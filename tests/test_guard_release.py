"""Disposable RSA keys and real TLS sockets; no device/policy/production writes."""
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

GUARD = Path(__file__).resolve().parents[1] / "tools/browser/site_scoped_youtube_guard"
sys.path.insert(0, str(GUARD))
import crx3
import installer_core as core
import release_core as release


def run_openssl(*args):
    # Fixtures must not inherit the runner's certificate extension sections or
    # OPENSSL_CONF override. Certificate requests receive our explicit profile.
    environment = dict(os.environ, OPENSSL_CONF=os.devnull)
    result = subprocess.run(["openssl", *map(str, args)], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, input=b"", env=environment,
                            check=False, timeout=30)
    if result.returncode:
        raise RuntimeError(f"Disposable OpenSSL fixture {args[0]} failed")
    return result.stdout


def write_json(path, value):
    path.write_bytes(core.pretty_json(value).encode())


class HTTPSFixture:
    """Real certificate validation with DNS redirected only inside the test."""
    def __init__(self, root, cert, key):
        self.root, self.routes, self.requests = root, {}, []
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                fixture.requests.append((self.path, dict(self.headers)))
                override = fixture.routes.get(self.path)
                if callable(override):
                    override = override(self.path)
                if override:
                    status, body, content_type, extra = override
                else:
                    file = fixture.root / self.path.lstrip("/")
                    if file.is_file():
                        status, body = 200, file.read_bytes()
                    else:
                        status, body = 404, b"missing"
                    content_type = ("application/xml" if self.path.endswith(".xml")
                                    else "application/x-chrome-extension")
                    extra = {}
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body) + extra.pop("truncate", 0)))
                for name, value in extra.items():
                    self.send_header(name, value)
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.origin = f"https://releases.school.test:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        original = socket.getaddrinfo

        def fixture_dns(host, port, *args, **kwargs):
            if host == "releases.school.test":
                host = "127.0.0.1"
            return original(host, port, *args, **kwargs)

        self.dns = patch("socket.getaddrinfo", side_effect=fixture_dns)
        self.dns.start()
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.dns.stop()


@unittest.skipUnless(shutil.which("openssl"), "OpenSSL 3 is required for CRX release acceptance")
class ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys_temp = tempfile.TemporaryDirectory(prefix="schoolops-disposable-keys-")
        cls.addClassCleanup(cls.keys_temp.cleanup)
        cls.keys = Path(cls.keys_temp.name)
        for name in ("signer", "other", "ca", "server"):
            run_openssl("genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048",
                        "-out", cls.keys / f"{name}.pem")
        for name in ("signer", "other"):
            run_openssl("pkey", "-in", cls.keys / f"{name}.pem", "-pubout",
                        "-out", cls.keys / f"{name}.pub")
        # OpenSSL 3.2+ supplies key identifiers automatically; older versions
        # and runner configs differ. Specify the complete CA and server profile
        # so certificate-chain validity never depends on those defaults.
        profile = cls.keys / "tls.cnf"
        profile.write_bytes(b"[req]\n"
                            b"prompt = no\n"
                            b"distinguished_name = ca_name\n"
                            b"default_md = sha256\n"
                            b"[ca_name]\n"
                            b"CN = SchoolOps disposable test CA\n"
                            b"[ca_extensions]\n"
                            b"basicConstraints = critical,CA:TRUE,pathlen:0\n"
                            b"keyUsage = critical,keyCertSign,cRLSign\n"
                            b"subjectKeyIdentifier = hash\n"
                            b"authorityKeyIdentifier = keyid:always,issuer\n"
                            b"[server_extensions]\n"
                            b"basicConstraints = critical,CA:FALSE\n"
                            b"keyUsage = critical,digitalSignature,keyEncipherment\n"
                            b"extendedKeyUsage = serverAuth\n"
                            b"subjectAltName = DNS:releases.school.test\n"
                            b"subjectKeyIdentifier = hash\n"
                            b"authorityKeyIdentifier = keyid:always,issuer\n")
        run_openssl("req", "-x509", "-new", "-key", cls.keys / "ca.pem", "-days", "1",
                    "-sha256", "-set_serial", "1", "-config", profile,
                    "-extensions", "ca_extensions", "-out", cls.keys / "ca.crt")
        run_openssl("req", "-new", "-key", cls.keys / "server.pem", "-sha256",
                    "-config", profile, "-subj", "/CN=releases.school.test",
                    "-out", cls.keys / "server.csr")
        run_openssl("x509", "-req", "-in", cls.keys / "server.csr", "-CA", cls.keys / "ca.crt",
                    "-CAkey", cls.keys / "ca.pem", "-set_serial", "2", "-days", "1", "-sha256",
                    "-extfile", profile, "-extensions", "server_extensions",
                    "-out", cls.keys / "server.crt")
        # Fail once at setup with the certificate operation identified, rather
        # than making every HTTPS acceptance case fail on an unusable fixture.
        # This is deliberately stricter than runtimes without strict defaults.
        run_openssl("verify", "-x509_strict", "-purpose", "sslserver", "-verify_hostname",
                    "releases.school.test", "-CAfile", cls.keys / "ca.crt", "-no-CApath",
                    cls.keys / "server.crt")
        cls.public = crx3.public_key_bytes(cls.keys / "signer.pub")
        cls.eid = crx3.extension_id(cls.public)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="schoolops-release-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.web = self.root / "web"
        self.web.mkdir()

    def bundle(self, name="bundle", version="1.2.3", **settings):
        target = self.root / name
        core.export_bundle({"allowed_embed_sites": ["portal.school.test"],
                            "allowed_sites": [], "blocked_sites": [], "mode": "blacklist",
                            "channel": "self_hosted", "update_url": "", "extension_version": version,
                            **settings}, target)
        return target

    def prepared(self, name="release", bundle=None, origin="https://releases.school.test",
                 version="1.2.3", previous=None, **overrides):
        bundle = bundle or self.bundle(name="bundle-" + name, version=version)
        options = {"public_key": self.keys / "signer.pub", "expected_id": self.eid,
                   "expected_version": version, "update_url": origin + "/updates.xml",
                   "crx_url": origin + f"/packages/guard-{version}.crx",
                   "initial_release": previous is None, "previous_release": previous}
        options.update(overrides)
        return release.prepare_release(bundle, self.root / name, **options)

    def signed(self, name="release", **kwargs):
        path = self.prepared(name, **kwargs)
        release.sign_release(path, self.keys / "signer.pem")
        return path

    def stage(self, path):
        plan = release.publication_plan(path, self.web)
        return release.stage_release(path, self.web, approve_plan_sha256=plan["approval_sha256"])

    @contextmanager
    def live(self):
        with HTTPSFixture(self.web, self.keys / "server.crt", self.keys / "server.pem") as server:
            bundle = self.bundle()
            path = self.signed(bundle=bundle, origin=server.origin)
            self.stage(path)
            yield server, bundle, path

    def test_reproducible_preparation_signing_and_external_signature_import(self):
        bundle = self.bundle()
        a, b = self.prepared("a", bundle=bundle), self.prepared("b", bundle=bundle)
        release.sign_release(a, self.keys / "signer.pem")
        payload = (b / "signing-input.bin").read_bytes()
        signature = run_openssl("dgst", "-sha256", "-sign", self.keys / "signer.pem",
                               "-out", self.root / "external.sig", b / "signing-input.bin")
        self.assertEqual(signature, b"")
        release.assemble_release(b, self.root / "external.sig")
        for filename in ("release.json", "extension.zip", "public-key.der", "signing-input.bin",
                         "extension.crx", "update.xml", "signed.json"):
            self.assertEqual((a / filename).read_bytes(), (b / filename).read_bytes(), filename)
        self.assertEqual((a / "extension.zip").read_bytes(), (bundle / "extension.zip").read_bytes())
        self.assertIn(b"CRX3 SignedData\x00", payload)
        self.assertFalse(any(b"PRIVATE KEY" in p.read_bytes() for p in a.iterdir() if p.is_file()))
        release.sign_release(a, self.keys / "signer.pem")

    def test_preparation_rejects_wrong_expected_id_and_version(self):
        bundle = self.bundle()
        for name, options, error in (
            ("id", {"expected_id": "a" * 32}, "ID"),
            ("version", {"expected_version": "9.9.9"}, "version"),
            ("private", {"public_key": self.keys / "signer.pem"}, "public key"),
        ):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, error):
                self.prepared(name, bundle=bundle, **options)
            self.assertFalse((self.root / name).exists())

    def test_web_store_route_and_explicit_initial_release(self):
        store = self.bundle(channel="web_store", update_url=core.WEBSTORE_URL)
        with self.assertRaisesRegex(ValueError, "Web Store"):
            self.prepared(bundle=store)
        bundle = self.bundle("self")
        with self.assertRaisesRegex(ValueError, "previous signed release"):
            self.prepared("no-baseline", bundle=bundle, initial_release=False)
        path = self.signed("prior", bundle=bundle)
        with self.assertRaisesRegex(ValueError, "previous signed release"):
            self.prepared("both", bundle=bundle, previous=path, initial_release=True)

    def test_updates_reject_downgrades_equal_aliases_and_changed_signing_identity(self):
        prior = self.signed(version="2")
        for index, value in enumerate(("1.9", "2", "2.0", "2.0.0.0")):
            with self.subTest(version=value), self.assertRaisesRegex(ValueError, "strictly increase"):
                self.prepared(f"bad-{index}", version=value, previous=prior)
        other_id = release.public_key_id(self.keys / "other.pub")
        with self.assertRaisesRegex(ValueError, "preserve.*identity"):
            self.prepared("other-key", version="3", previous=prior,
                          public_key=self.keys / "other.pub", expected_id=other_id)
        with self.assertRaisesRegex(ValueError, "new immutable CRX URL"):
            self.prepared("reused-path", version="3", previous=prior,
                          crx_url="https://releases.school.test/packages/guard-2.crx")

    def test_invalid_urls_fail_before_output(self):
        bundle = self.bundle()
        invalid = ("http://releases.school.test/a.xml", "https://user:pass@releases.school.test/a.xml",
                   "https://releases.school.test/a.xml?x=1", "https://releases.school.test/a.xml#x",
                   "https://releases.school.test/a/../b.xml", "https://releases.school.test/%2e%2e/a.xml",
                   "https://releases.school.test/a\\b.xml", "https://releases.school.test:bad/a.xml")
        for index, value in enumerate(invalid):
            with self.subTest(url=value), self.assertRaises(ValueError):
                self.prepared(str(index), bundle=bundle, update_url=value)
        with self.assertRaisesRegex(ValueError, "same approved HTTPS origin"):
            self.prepared("origin", bundle=bundle, crx_url="https://other.school.test/a.crx")

    def test_frozen_bundle_tampering_and_unauthorized_version_change(self):
        bundle = self.bundle()
        archive = bundle / "extension.zip"
        archive.write_bytes(archive.read_bytes() + b"tamper")
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.prepared(bundle=bundle)
        path = self.prepared("good")
        plan = json.loads((path / "release.json").read_bytes())
        plan["extension_version"] = "9"
        plan["release_id"] = release._plan_id(plan)
        write_json(path / "release.json", plan)
        with self.assertRaisesRegex(ValueError, "Unauthorized version"):
            release.sign_release(path, self.keys / "signer.pem")

    def test_external_signer_cannot_substitute_key_payload_or_signature(self):
        path = self.prepared()
        with self.assertRaisesRegex(ValueError, "OpenSSL rejected"):
            release.sign_release(path, self.keys / "other.pem")
        self.assertFalse((path / "extension.crx").exists())
        signature = crx3.sign_payload(b"different payload", self.keys / "signer.pem")
        with self.assertRaisesRegex(ValueError, "OpenSSL rejected"):
            release.assemble_release(path, signature)
        with self.assertRaisesRegex(ValueError, "wrong size"):
            release.assemble_release(path, b"bad")
        source = path / "signing-input.bin"
        source.write_bytes(source.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "Signing input"):
            release.sign_release(path, self.keys / "signer.pem")

    def test_crx_rejects_malformed_signature_header_identity_and_zip(self):
        path = self.signed()
        original = (path / "extension.crx").read_bytes()
        archive = (path / "extension.zip").read_bytes()
        header_size = struct.unpack("<I", original[8:12])[0]
        cases = {"magic": b"BAD!" + original[4:], "version": original[:4] + struct.pack("<I", 2) + original[8:],
                 "large-header": original[:8] + struct.pack("<I", crx3.MAX_HEADER_BYTES + 1) + original[12:],
                 "truncated": original[:25], "zip": original[:-1] + bytes([original[-1] ^ 1]),
                 "signature": original[:400] + bytes([original[400] ^ 1]) + original[401:]}
        for marker in (b"PK\x05\x06", b"PK\x06\x07", b"PK\x06\x06"):
            cases[repr(marker)] = original[:20] + marker + original[24:]
        header = original[12:12 + header_size]
        bad = header + crx3._field(10000, crx3.signed_header(self.public))
        cases["duplicate"] = original[:8] + struct.pack("<I", len(bad)) + bad + archive
        bad = header + crx3._field(99, b"unknown")
        cases["unknown"] = original[:8] + struct.pack("<I", len(bad)) + bad + archive
        for name, crx in cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                crx3.verify(crx, expected_zip=archive, expected_key=self.public, expected_id=self.eid)
        with self.assertRaisesRegex(ValueError, "identity"):
            crx3.verify(original, expected_zip=archive, expected_key=self.public, expected_id="a" * 32)

    def test_valid_signature_over_other_configuration_is_rejected(self):
        one = self.signed("one")
        two_bundle = self.bundle("two-bundle", allowed_embed_sites=["different.school.test"])
        two = self.signed("two", bundle=two_bundle)
        with self.assertRaisesRegex(ValueError, "ZIP fingerprint"):
            crx3.verify((two / "extension.crx").read_bytes(), expected_zip=(one / "extension.zip").read_bytes(),
                        expected_key=self.public, expected_id=self.eid)

    def test_rezipped_archive_even_with_same_files_is_refused(self):
        path = self.prepared()
        stream = io.BytesIO()
        with zipfile.ZipFile(path / "extension.zip") as source, zipfile.ZipFile(stream, "w") as out:
            for name in source.namelist():
                out.writestr(name, source.read(name))
        with self.assertRaisesRegex(ValueError, "exact compiled"):
            release._archive_settings(stream.getvalue())

    def test_staging_requires_exact_review_and_only_copies_publication_files(self):
        path = self.signed()
        plan = release.publication_plan(path, self.web)
        self.assertEqual([x["mode"] for x in plan["writes"]], ["immutable", "atomic_replace"])
        with self.assertRaisesRegex(ValueError, "approve that exact"):
            release.stage_release(path, self.web, approve_plan_sha256="0" * 64)
        self.assertEqual(list(self.web.iterdir()), [])
        status = self.stage(path)
        self.assertFalse(status["remote_verified"])
        self.assertFalse(status["policy_applied"])
        self.assertFalse(status["managed_device_enforcement"])
        files = {p.relative_to(self.web).as_posix() for p in self.web.rglob("*") if p.is_file()}
        self.assertEqual(files, {"updates.xml", "packages/guard-1.2.3.crx", ".schoolops-release.lock"})
        self.stage(path)

    def test_staging_uses_the_exact_approved_snapshot_despite_source_replacement(self):
        bundle = self.bundle()
        path = self.signed("approved", bundle=bundle)
        substitute = self.signed("unapproved", bundle=bundle,
                                 update_url="https://releases.school.test/unapproved.xml",
                                 crx_url="https://releases.school.test/unapproved.crx")
        plan = release.publication_plan(path, self.web)
        good, bad = release._signed(path), release._signed(substitute)
        reads = []

        def switched(_):
            reads.append(True)
            return good if len(reads) == 1 else bad

        with patch.object(release, "_signed", side_effect=switched):
            release.stage_release(path, self.web, approve_plan_sha256=plan["approval_sha256"])
        self.assertEqual(len(reads), 1)
        self.assertTrue((self.web / "updates.xml").is_file())
        self.assertFalse((self.web / "unapproved.xml").exists())
        self.assertFalse((self.web / "unapproved.crx").exists())

    def test_package_first_interruption_preserves_predecessor_and_recovers(self):
        prior = self.signed("prior", version="1")
        self.stage(prior)
        old_manifest = (self.web / "updates.xml").read_bytes()
        new = self.signed("new", version="2", previous=prior)
        original = release._atomic_file

        def interrupt(path, data, *, immutable):
            if not immutable:
                raise OSError("simulated interruption before manifest commit")
            return original(path, data, immutable=immutable)

        with patch.object(release, "_atomic_file", side_effect=interrupt):
            with self.assertRaisesRegex(OSError, "interruption"):
                self.stage(new)
        self.assertEqual((self.web / "updates.xml").read_bytes(), old_manifest)
        self.assertEqual((self.web / "packages/guard-2.crx").read_bytes(), (new / "extension.crx").read_bytes())
        self.stage(new)
        self.assertEqual((self.web / "updates.xml").read_bytes(), (new / "update.xml").read_bytes())
        with self.assertRaisesRegex(ValueError, "predecessor"):
            self.stage(prior)

    def test_crash_after_manifest_commit_is_recoverable_and_idempotent(self):
        path = self.signed()
        original = release._atomic_file

        def after_commit(target, data, *, immutable):
            original(target, data, immutable=immutable)
            if not immutable:
                raise OSError("receipt lost after commit")

        with patch.object(release, "_atomic_file", side_effect=after_commit), self.assertRaises(OSError):
            self.stage(path)
        self.stage(path)
        self.assertEqual((self.web / "updates.xml").read_bytes(), (path / "update.xml").read_bytes())

    def test_real_process_interruption_releases_lock_and_recovers(self):
        path = self.signed()
        program = """import os, sys
sys.path.insert(0, sys.argv[1])
import release_core as r
original = r._atomic_file
def interrupted(path, data, *, immutable):
    original(path, data, immutable=immutable)
    if immutable:
        os._exit(23)
r._atomic_file = interrupted
p = r.publication_plan(sys.argv[2], sys.argv[3])
r.stage_release(sys.argv[2], sys.argv[3], approve_plan_sha256=p['approval_sha256'])
"""
        result = subprocess.run([sys.executable, "-c", program, str(GUARD), str(path), str(self.web)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        self.assertEqual(result.returncode, 23, result.stderr.decode())
        self.assertFalse((self.web / "updates.xml").exists())
        self.assertTrue((self.web / "packages/guard-1.2.3.crx").is_file())
        self.stage(path)

    def test_interrupted_signing_resumes_only_matching_artifacts(self):
        path = self.prepared()
        original = release._atomic_file

        def interrupt(target, data, *, immutable):
            if target.name == "signed.json":
                raise OSError("signing receipt interrupted")
            return original(target, data, immutable=immutable)

        with patch.object(release, "_atomic_file", side_effect=interrupt), self.assertRaises(OSError):
            release.sign_release(path, self.keys / "signer.pem")
        with self.assertRaises(ValueError):
            release.publication_plan(path, self.web)
        release.sign_release(path, self.keys / "signer.pem")
        (path / "extension.crx").write_bytes(b"conflict")
        with self.assertRaisesRegex(ValueError, "different bytes"):
            release.sign_release(path, self.keys / "signer.pem")

    def test_staging_refuses_conflict_changed_approval_and_concurrent_writer(self):
        path = self.signed()
        plan = release.publication_plan(path, self.web)
        (self.web / "updates.xml").write_bytes(b"unrelated manifest")
        with self.assertRaisesRegex(ValueError, "predecessor"):
            release.stage_release(path, self.web, approve_plan_sha256=plan["approval_sha256"])
        (self.web / "updates.xml").unlink()
        with release._lock(self.web), self.assertRaisesRegex(ValueError, "publisher"):
            self.stage(path)
        (self.web / "packages").mkdir()
        (self.web / "packages/guard-1.2.3.crx").write_bytes(b"conflicting package")
        with self.assertRaisesRegex(ValueError, "conflicting package"):
            self.stage(path)
        self.assertFalse((self.web / "updates.xml").exists())

    def test_staging_refuses_symlink_destinations(self):
        if os.name == "nt":
            self.skipTest("Unprivileged Windows symlink creation varies by runner")
        path = self.signed()
        outside = self.root / "outside"
        outside.mkdir()
        (self.web / "packages").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.stage(path)
        self.assertEqual(list(outside.iterdir()), [])

    def test_real_https_verification_and_wizard_handoff_are_not_enforcement(self):
        with self.live() as (server, bundle, path):
            receipt = release.verify_publication(path, ca_file=self.keys / "ca.crt")
            self.assertEqual(receipt["extension_id"], self.eid)
            self.assertTrue(release.publication_admitted(receipt["verification"]))
            self.assertFalse(receipt["policy_applied"])
            self.assertFalse(receipt["managed_device_enforcement"])
            self.assertEqual(receipt["extension_zip_sha256"], hashlib.sha256((bundle / "extension.zip").read_bytes()).hexdigest())
            deployment = self.root / "deployment"
            with patch.object(core.platform_policy, "apply_linux_policy_content", side_effect=AssertionError("policy must not run")):
                release.export_verified_deployment(bundle, path, deployment, ca_file=self.keys / "ca.crt", target_os="windows")
            _, resumed = core.load_bundle(deployment)
            self.assertEqual(resumed["publication_receipt"]["scope"], "downloaded_release_bytes")
            self.assertEqual(resumed["target_os"], "windows")
            policy = json.loads(core.verify_policy_bundle(deployment))
            self.assertTrue(policy["ExtensionSettings"][self.eid]["override_update_url"])
            self.assertEqual((deployment / "extension.zip").read_bytes(), (bundle / "extension.zip").read_bytes())
            self.assertTrue(all("Cookie" not in headers and "Authorization" not in headers
                                for _, headers in server.requests))

    def test_tls_ca_and_hostname_verification_cannot_be_disabled(self):
        with self.live() as (_, _bundle, path):
            with self.assertRaisesRegex(ValueError, "HTTPS publication download failed"):
                release.verify_publication(path)
            wrong = release.load_release(path)["update_url"].replace("releases.school.test", "127.0.0.1")
            with self.assertRaisesRegex(ValueError, "HTTPS publication download failed"):
                release._https_get(wrong, ca_file=self.keys / "ca.crt", limit=4096,
                                   expected_types={"application/xml"})

    def test_wrong_remote_id_version_fingerprint_url_and_missing_manifest(self):
        with self.live() as (server, bundle, path):
            xml = (path / "update.xml").read_bytes()
            original_sha = hashlib.sha256((path / "extension.crx").read_bytes()).hexdigest().encode()
            variants = (("id", xml.replace(self.eid.encode(), b"a" * 32), "extension ID"),
                        ("version", xml.replace(b'version="1.2.3"', b'version="9.9.9"'), "version"),
                        ("fingerprint", xml.replace(original_sha, b"0" * 64), "fingerprint"),
                        ("url", xml.replace(b"/packages/", b"/substitute/"), "URL"),
                        ("namespace", xml.replace(b"update2/response", b"other/response"), "namespace"),
                        ("DTD", b'<!DOCTYPE x [<!ENTITY a "x">]>' + xml, "DTD"),
                        ("malformed", b"<xml", "valid UTF-8"))
            for name, body, message in variants:
                server.routes["/updates.xml"] = (200, body, "application/xml", {})
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, message):
                    release.verify_publication(path, ca_file=self.keys / "ca.crt")
            for status in (404, 403, 500):
                server.routes["/updates.xml"] = (status, b"missing", "application/xml", {})
                with self.subTest(status=status), self.assertRaisesRegex(ValueError, "download failed"):
                    release.export_verified_deployment(bundle, path, self.root / f"bad-{status}",
                                                       ca_file=self.keys / "ca.crt")
                self.assertFalse((self.root / f"bad-{status}").exists())

    def test_failed_wrong_and_interrupted_package_downloads(self):
        with self.live() as (server, _bundle, path):
            crx = (path / "extension.crx").read_bytes()
            variations = ((404, b"missing", {}, "download failed"),
                          (500, b"failed", {}, "download failed"),
                          (200, crx[:-20], {"truncate": 20}, "interrupted"),
                          (200, crx + b"changed", {}, "fingerprint"))
            for index, (status, body, headers, message) in enumerate(variations):
                server.routes["/packages/guard-1.2.3.crx"] = (status, body, "application/x-chrome-extension", headers)
                with self.subTest(index=index), self.assertRaisesRegex(ValueError, message):
                    release.verify_publication(path, ca_file=self.keys / "ca.crt")
            server.routes.clear()
            receipt = release.verify_publication(path, ca_file=self.keys / "ca.crt")
            self.assertTrue(release.publication_admitted(receipt["verification"]))

    def test_redirects_wrong_content_types_and_encoded_responses_are_refused(self):
        with self.live() as (server, _, path):
            xml = (path / "update.xml").read_bytes()
            cases = ((302, b"", "application/xml", {"Location": "http://other.test/updates.xml"}, "redirect"),
                     (302, b"", "application/xml", {"Location": server.origin + "/other.xml"}, "redirect"),
                     (200, xml, "text/html", {}, "Content-Type"),
                     (200, xml, "application/xml", {"Content-Encoding": "gzip"}, "unencoded"),
                     (200, b"X" * (release.MAX_MANIFEST_BYTES + 1), "application/xml", {}, "size limit"))
            for status, body, kind, headers, message in cases:
                server.routes["/updates.xml"] = (status, body, kind, headers)
                with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                    release.verify_publication(path, ca_file=self.keys / "ca.crt")

    def test_cookies_are_not_replayed_and_manifest_change_prevents_receipt(self):
        with self.live() as (server, _, path):
            xml = (path / "update.xml").read_bytes()
            server.routes["/updates.xml"] = (200, xml, "application/xml", {"Set-Cookie": "operator=secret"})
            release.verify_publication(path, ca_file=self.keys / "ca.crt")
            self.assertTrue(all("Cookie" not in headers for _, headers in server.requests))
            calls = []

            def changed(_):
                calls.append(True)
                return (200, xml if len(calls) == 1 else xml + b"\n", "application/xml", {})

            server.routes["/updates.xml"] = changed
            with self.assertRaisesRegex(ValueError, "changed during"):
                release.verify_publication(path, ca_file=self.keys / "ca.crt")

    def test_deployment_rejects_release_for_different_prepared_config_before_network(self):
        path = self.signed()
        other = self.bundle("other", allowed_embed_sites=["different.school.test"])
        with patch.object(release, "verify_publication", side_effect=AssertionError("must not fetch")):
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                release.export_verified_deployment(other, path, self.root / "bad")
        self.assertFalse((self.root / "bad").exists())

    def test_admission_uses_all_strict_boolean_guards(self):
        import itertools
        admitted = []
        for values in itertools.product((False, True), repeat=len(release.GUARDS)):
            guards = dict(zip(release.GUARDS, values))
            if release.publication_admitted(guards):
                admitted.append(values)
        self.assertEqual(admitted, [(True,) * 8])
        for key in release.GUARDS:
            guards = dict.fromkeys(release.GUARDS, True)
            guards[key] = 1
            self.assertFalse(release.publication_admitted(guards))
        self.assertFalse(release.publication_admitted(dict.fromkeys(release.GUARDS[:-1], True)))

    def test_cli_key_id_and_signing_errors_are_noninteractive(self):
        result = subprocess.run([sys.executable, str(GUARD / "release_core.py"), "key-id",
                                 str(self.keys / "signer.pub")], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), self.eid)
        path = self.prepared()
        result = subprocess.run([sys.executable, str(GUARD / "release_core.py"), "sign", str(path),
                                 "--key", str(self.keys / "other.pem")],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Release refused", result.stderr)
        self.assertNotIn(str(self.keys), result.stderr)

    def test_cli_operation_reports_preserve_review_and_failures_for_windowed_apps(self):
        path = self.prepared()
        report = self.root / "operation.json"
        command = [sys.executable, str(GUARD / "release_core.py"), "--report", str(report),
                   "sign", str(path), "--key"]
        failed = subprocess.run(command + [str(self.keys / "other.pem")], capture_output=True, timeout=10)
        self.assertEqual(failed.returncode, 1)
        result = json.loads(report.read_bytes())
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("PRIVATE KEY", report.read_text())
        passed = subprocess.run(command + [str(self.keys / "signer.pem")], capture_output=True, timeout=10)
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertEqual(json.loads(report.read_bytes())["status"], "passed")
        original_plan = (path / "release.json").read_bytes()
        bad = subprocess.run([sys.executable, str(GUARD / "release_core.py"), "--report",
                              str(path / "release.json"), "sign", str(path), "--key",
                              str(self.keys / "signer.pem")], capture_output=True, timeout=10)
        self.assertEqual(bad.returncode, 1)
        self.assertEqual((path / "release.json").read_bytes(), original_plan)
        report.write_bytes(b"an unrelated operator file")
        rejected = subprocess.run(command + [str(self.keys / "signer.pem")], capture_output=True, timeout=10)
        self.assertEqual(rejected.returncode, 1)
        self.assertEqual(report.read_bytes(), b"an unrelated operator file")


if __name__ == "__main__":
    unittest.main()
