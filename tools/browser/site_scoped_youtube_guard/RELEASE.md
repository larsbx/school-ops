# Reproducible self-hosted CRX release

This workflow turns the wizard's **exact prepared ZIP** into a signed CRX3,
prepares an HTTPS update manifest, and verifies downloaded publication bytes
before exporting a self-hosted deployment bundle. It supports a local OpenSSL
signer or an externally produced RSA signature. The Chrome Web Store route
remains available in the [setup guide](README.md).

The implementation and CI use disposable credentials and controlled HTTPS
fixtures. No production key, actual school hostname, production extension,
managed device or policy rollout is established by those checks.

## Authority and observation boundaries

Preparation needs only a **public** key. The GUI never requests a private key,
publishes files, or enrolls a device. Its **Verify HTTPS & export** action makes
anonymous read-only requests and exports local files. Applying policy remains a
separate explicit administrator action with the existing operating-system
protections.

Before a production operation, separately approve the exact key/signing tool,
extension ID, version, source ZIP hash, destination URLs and publication actions.
Local staging has a concrete review/approval mechanism described below. Remote
upload, production key access, device enrollment and enterprise-policy changes
are not automated by this release workflow.

An unsigned receipt records what the verifier observed. Its local shape and
binding checks do not authenticate the person who created it. It is not a
security token, proof of future availability, or proof of browser enforcement.
To check an endpoint again, run the verifier again. Preserve the trusted prepared
bundle and release directory; hashes supplied only by an untrusted remote server
are never used as the expected fingerprint.

## Requirements and supported profile

- Source use needs Python 3.11+ and OpenSSL 3 on the signing/verification
  workstation. Native bundles include Python; OpenSSL remains an external
  workstation dependency, checked when the release operation runs.
  On macOS with Homebrew OpenSSL 3 installed, prepend
  `$(brew --prefix openssl@3)/bin` to `PATH` before launching the source or native
  command. Confirm `openssl version` reports OpenSSL 3; the system or Python
  toolchain can otherwise select another OpenSSL installation. Hosted macOS
  acceptance explicitly selects Homebrew OpenSSL 3 and checks the major version.
- Supported signing keys are RSA 2048–8192-bit public SubjectPublicKeyInfo keys.
  Public keys may be PEM or DER. The local signer uses an unencrypted local PEM
  through an explicitly supplied path; it does not collect passwords or copy
  the key. Use the external-signature route for a protected signer/HSM.
- The deliberately narrow CRX3 profile has one RSA/SHA-256 PKCS#1 v1.5 proof and
  canonical protobuf encoding. It does not accept arbitrary third-party CRX
  headers or claim a Chrome Web Store publisher signature.
- Update XML and CRX URLs must be explicit HTTPS file URLs on the same origin,
  without credentials, queries, fragments, redirects or path traversal. Use a
  new CRX URL for each version. The update URL remains stable.
- XML must be served as `application/xml` or `text/xml`; CRX must be served as
  `application/x-chrome-extension`. Serve unencoded exact bytes, anonymously,
  without cookies or authentication. The verifier does not inherit browser
  sessions, proxy credentials or environment proxy configuration.
- Downloads have size and time bounds. Normal TLS trust and hostname checking
  are mandatory. `--ca-file` supplies an explicitly selected private/test CA
  bundle; it does not disable certificate or hostname verification.

## Wizard handoff

1. Choose **self_hosted** before the initial bundle export. Prepare the school
   websites, rules and version into a new folder. Reopen that `setup.json`.
2. Choose **Prepare self-hosted release…**. Select the public key and pin the
   expected extension ID, exact prepared version, update URL and package URL.
   Select the previous signed release, or explicitly declare the first release.
3. The app writes a new release directory and copies a signing command. A
   separate authorized signer runs that command or supplies a detached signature.
   The command writes a sibling JSON operation report, including failures, so
   windowed native applications do not hide the result.
4. Review the release and exact publication plan. After separate approval,
   stage/upload the immutable CRX first and activate the update manifest last.
5. Choose **Verify HTTPS & export…**, select the signed release, and choose a new
   deployment directory. Verification downloads the manifest and CRX, compares
   them with the prepared release, verifies the signature and embedded ZIP, and
   fetches the manifest again to detect changes during the check.
6. The app reopens the resulting deployment. Follow its existing policy and
   on-device verification steps after separately approving those actions.

The distribution channel, school configuration and extension version stay
bound to the saved bundle. The target OS may change without rebuilding the ZIP.
Long-running release operations run off the UI thread; navigation and policy
actions remain locked to the original bundle until the operation finishes.

New self-hosted exports and installation require a bound verification receipt.
Old operator-attested self-hosted bundles still reopen and support removal of an
unchanged policy owned by the installer. They need release verification before
new installation. Existing Web Store confirmation behavior is preserved.

## Command-line preparation and signing

The following are **review examples**, using reserved `.example` URLs. They are
not authorization to access a production key or publish to a real host. Run
source commands from this directory, replacing paths with reviewed inputs.

Derive the public-key ID, then compare it with the independently pinned identity
for an existing deployment:

```sh
python release_core.py key-id approved-public-key.pem
```

Prepare the first release from a saved self-hosted wizard bundle:

```sh
python release_core.py prepare prepared/ release-0.1.1/ \
  --public-key approved-public-key.pem \
  --expected-id abcdefghijklmnopabcdefghijklmnop \
  --expected-version 0.1.1 \
  --update-url https://updates.school.example/guard/updates.xml \
  --crx-url https://updates.school.example/guard/packages/guard-0.1.1.crx \
  --initial-release
```

The example ID is illustrative and is refused unless it matches the actual
public key. `--expected-version` must exactly match the frozen extension
manifest. Preparation refuses a changed bundle, inconsistent ID, missing
history declaration, or an existing output directory.

After separately authorizing the signer/key operation:

```sh
python release_core.py --report release-0.1.1-signing-result.json \
  sign release-0.1.1/ --key approved-signing-key.pem
```

For an external signer, have the approved signing tool sign the **exact**
`signing-input.bin` with RSA PKCS#1 v1.5 and SHA-256, then import its detached
signature:

```sh
python release_core.py assemble release-0.1.1/ --signature approved-signature.bin
```

The integration verifies the signature itself. A signer cannot supply trusted
verification flags, substitute a key, rezip the archive, modify the version,
change rules or add extension files. Repeating signing with the same inputs
reuses identical output; conflicting existing bytes are refused.

The native executable accepts the same commands after `--release`. A windowed
native invocation must put `--report <sibling-file.json>` before the subcommand.
Reports can replace previous SchoolOps operation reports; unrelated files and
paths inside the prepared, release or staging directory are refused.

## Reviewable publication and interrupted recovery

The local staging adapter maps the URL paths beneath a selected existing
web-root. It does not make HTTP PUTs, SSH connections, cloud-storage writes or
other uploads. Keep this directory under one publisher's control.

First show the exact paths, URLs, hashes, sizes, order and current predecessor:

```sh
python release_core.py plan-stage release-0.1.1/ reviewed-staging-root/
```

Only after reviewing and separately approving that output, pass its exact
`approval_sha256`:

```sh
python release_core.py stage release-0.1.1/ reviewed-staging-root/ \
  --approve-plan-sha256 APPROVED_PLAN_SHA256
```

The approval is bound to one verified in-memory snapshot. Replacing the release
directory while staging cannot change the approved files or destinations.
Staging copies only the CRX and update XML, never signing inputs, keys, saved
setup files or operator receipts.

| Interruption point | State and recovery |
| --- | --- |
| Before package insertion | The previous manifest remains active; rebuild the plan and retry. |
| After package insertion, before manifest replacement | The complete immutable package may exist, but the previous manifest is still active. Retry checks the existing bytes before activating the new manifest. |
| After manifest replacement, before reporting success | Rebuild the plan and retry. Identical package/manifest bytes are accepted idempotently; the HTTPS check is still required. |
| During signing before `signed.json` | Staging refuses the incomplete release. Repeating the same signing operation validates existing output and writes the commit record last. |
| Conflicting bytes or unexpected predecessor | Stop and inspect. The workflow does not overwrite an immutable package or silently reset release history. |

Files are written through a temporary file, flushed, then inserted/replaced
atomically on the same filesystem. Immutable insertion uses hard links, so the
staging filesystem must support them. Directory flushes are performed on POSIX;
power-loss durability on all storage devices is not proved. Process interruption
recovery is tested, including an actual child-process termination.

An OS advisory lock serializes cooperating publishers and is released when a
process dies. It does not exclude unrelated writers that ignore the lock. The
predecessor recheck and replacement are not a compare-and-swap transaction
against such writers. Use one authorized publisher for this directory. An
external hosting adapter must provide equivalent immutable-package and
manifest-last behavior; that external adapter is not established by these tests.

For remote publication, review the two `writes` entries with the operator who
owns the hosting system and obtain separate approval for their upload. Upload
the package first, confirm its completion, then activate the XML. Do not upload
the entire private release directory. This repository contains no production
hosting credentials or automatic production publishing workflow.

## Verify and export

```sh
python release_core.py verify release-0.1.1/
python release_core.py export-deployment prepared/ release-0.1.1/ deployment/ \
  --target-os windows
```

Both operations make fresh anonymous HTTPS requests. Export performs its own
check rather than accepting a previous report as a trusted verifier result.
The manifest ID, version, URL, size and package hash must match the local
release contract. The downloaded CRX must match the local signed CRX byte for
byte. Its public key, signed ID and signature are checked, and its complete ZIP
tail must equal the original prepared ZIP, which is recompiled from its saved
configuration. XML declarations/DTD tricks, duplicate entries, unsupported
headers, redirects, untrusted certificates and interrupted downloads fail.

Matching first and second manifest observations detect changes seen during the
check; they cannot exclude a change-and-change-back between requests. A receipt
therefore states `scope: downloaded_release_bytes`, `policy_applied: false` and
`managed_device_enforcement: false`.

## Updating versions

Prepare a new wizard configuration with a higher version, retain the same key
and extension ID, use a new immutable CRX URL, and pass
`--previous-release <previous-signed-release>` instead of `--initial-release`.
The previous signed files are revalidated. Versions compare numerically after
padding to four components: `1`, `1.0` and `1.0.0.0` are equal. Downgrades and
numerically equal versions are refused, even when their text differs.

The stable manifest must still match the supplied predecessor before staging a
new release. Omitting known history by claiming a first release is an operator
error; initial staging refuses an existing unrelated manifest rather than
overwriting it. This is not a global release registry or protection against an
administrator deliberately deleting history and the server's files.

The prepared manifest is never rewritten to insert an `update_url`. This
managed self-hosted route retains `ExtensionSettings.override_update_url: true`
and the existing OS management prerequisites. The release mechanism does not
establish unmanaged installation or relax the Windows/macOS management rules.

## Artifact inventory

| File | Meaning |
| --- | --- |
| `release.json` | Deterministic ID/version/ZIP/public-key/URL/predecessor contract and its hash |
| `extension.zip` | The original wizard publication ZIP, unchanged |
| `public-key.der` | Public RSA signing identity |
| `signing-input.bin` | CRX3 context, signed ID and exact ZIP; input for the approved signer |
| `extension.crx` | Deterministic, independently verified developer-signed CRX3 |
| `update.xml` | Deterministic update manifest with exact ID, version, CRX URL, size and hash |
| `signed.json` | Local commit record binding CRX and XML hashes; written last |
| `.schoolops-release.lock` | Advisory-lock file, not a progress or success record |
| Deployment `publication-receipt.json` | Timestamped, unsigned observation also bound in `setup.json`; not a policy or enforcement result |

Private signing keys and TLS fixture keys never belong in these artifacts.
Determinism applies to preparation, signing and XML for fixed inputs, not to the
observation timestamp or freshly generated disposable test keys.

## Automated acceptance and formal scope

Run concrete acceptance from the repository root:

```sh
python -m unittest discover -s tests -p 'test_guard_release*.py' -v
python tools/browser/site_scoped_youtube_guard/acceptance/check_crx_interop.py \
  --chromium /path/to/chrome --report /tmp/schoolops-crx-interop.json
```

The [release workflow](../../../.github/workflows/youtube-guard-release.yml)
runs real disposable signing and HTTPS acceptance on Windows, macOS and Linux,
then runs the pinned Lean/Quint verification separately. The existing browser
workflow checks the actual Chromium packer; native builds exercise the GUI and
packaged modules. Test credentials are generated in temporary directories and
are not uploaded as artifacts.

Concrete tests cover wrong identities, wrong package/configuration hashes,
unauthorized versions and numeric aliases, missing XML, failed/truncated
downloads, TLS and hostname failures, redirects, changed manifests, signer
substitution, malformed CRX, stale predecessors, conflicting immutable paths,
approval substitution, concurrent cooperating publishers, and interrupted
signing/publication recovery. The Chromium check independently compares actual
packer bytes with the OpenSSL adapter's output.

See the [formal verification boundary](formal/README.md) for the 44 registered
Lean theorems, compiled axiom audit, exact finite Quint closure, negative
controls, and the complete 256-case Python/Lean/Quint admission comparison.
Those results establish an abstract state machine and the small Boolean
admission projection. Cryptography, TLS, parsing, filesystem durability and the
complete Python implementation remain separately tested trust boundaries.

Passing release mechanics does not establish actual managed installation,
standard-user enforcement, real YouTube playback, or production hosting.

## Protocol references

- [Chromium CRX creator](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/crx_file/crx_creator.cc)
- [Chromium CRX verifier](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/crx_file/crx_verifier.cc)
- [CRX3 protobuf schema](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/crx_file/crx3.proto)
- [Extension ID derivation](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/crx_file/id_util.cc)
- [Self-hosting and update XML](https://developer.chrome.com/docs/extensions/how-to/distribute/host-on-linux)
- [Chrome version rules](https://developer.chrome.com/docs/extensions/reference/manifest/version)
- [Chromium ExtensionSettings policy](https://chromium.googlesource.com/chromium/src/+/HEAD/components/policy/resources/templates/policy_definitions/Extensions/ExtensionSettings.yaml)

Protocol references checked on 2026-11-11. Chromium's creator/verifier use
`RSA_PKCS1_SHA256`; the RSA-PSS comment in the protobuf file does not describe the
current implemented signing scheme.
