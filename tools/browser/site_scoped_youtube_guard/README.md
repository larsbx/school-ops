# SchoolOps Chrome setup — Site-Scoped YouTube Guard

The setup app prepares the Chrome extension, keeps its website configuration
attached to the exact publication package, and guides enterprise policy
installation. The extension allows YouTube **embeds on approved top-level school
websites** and blocks standalone YouTube navigation. It requires **Chrome 145+**.

**Current status:** prototype; no published SchoolOps extension listing, signed
production installer, real approved school hostname, or managed-device rollout
is established here. The source configuration still uses the reserved
`approved-site.invalid` placeholder. This is a device/browser utility, not a
curriculum readiness record or a biz-kit authorization mechanism.

## Start the setup app

The [native build workflow](https://github.com/larsbx/school-ops/actions/workflows/youtube-guard-native.yml)
creates **unsigned candidates** for Windows, macOS and Linux. Open a successful
run for the revision you intend to use, then download its matching artifact:

| Device | Artifact | Open after extraction |
| --- | --- | --- |
| Windows | `schoolops-youtube-guard-windows-2025-unsigned` | Extract `SchoolOps-YouTube-Guard-Setup-windows-unsigned.zip`, then open `SchoolOps-YouTube-Guard-Setup/SchoolOps-YouTube-Guard-Setup.exe` |
| macOS | `schoolops-youtube-guard-macos-15-unsigned` | Extract the contained tarball and open `SchoolOps-YouTube-Guard-Setup.app` |
| Linux | `schoolops-youtube-guard-ubuntu-24.04-unsigned` | Extract `SchoolOps-YouTube-Guard-Setup-linux-unsigned.tar.gz`, then run `SchoolOps-YouTube-Guard-Setup/SchoolOps-YouTube-Guard-Setup` |

Keep the **whole extracted application directory**, including its `_internal`
folder, together on Windows and Linux. Do not move or distribute the executable
alone. macOS likewise needs the complete `.app` bundle.

Check the source commit and architecture in `build-report.json`, and the file
hash in `SHA256SUMS.txt`. These are CI artifacts with limited retention, not a
permanent “latest installer” release channel. The native app includes Python;
operators do not need to install Python separately.

Unsigned candidates may be blocked by Windows SmartScreen or macOS Gatekeeper.
Use an organization-approved, signed distribution before rollout; this setup does
not recommend bypassing those controls. Preparation runs without administrator
rights. Only an explicit local policy action requests elevation.

For development from a repository checkout:

```sh
python3 tools/browser/site_scoped_youtube_guard/wizard.py
```

Windows also has [launch-wizard.cmd](launch-wizard.cmd); Linux/macOS have
[launch-wizard.sh](launch-wizard.sh). The source version needs Python 3 and Tkinter
(on some Linux distributions, the `python3-tk` package). Its setup flow needs no
third-party Python packages.

## Prepare → publish → install

### 1. Prepare the extension once

In **School websites**, enter the actual school portal hostnames, one per line.
Use hostnames such as `portal.example.org`, without a URL prefix or wildcard.
A listed hostname includes its subdomains; YouTube cannot be an approved portal.

In **Access rules**, choose:

- **Blacklist:** allow ordinary websites except those explicitly blocked.
- **Whitelist:** allow top-level navigation only to the school portals and the
  additional allowed hostnames.

Direct YouTube navigation stays blocked in either mode. On **Publication**, choose
the intended device OS and distribution channel. Leave the published extension
ID empty for this first preparation. Review the configuration and export to a
**new folder**. The setup app then opens **Install & verify**, with links to the
bundle folder and its `START_HERE.html` guide.

### 2. Publish that exact package

For the Chrome Web Store route, upload `extension.zip` through your own
[Chrome Web Store developer account](https://chrome.google.com/webstore/devconsole).
The ZIP has `manifest.json` at its root. Complete the publication process and
obtain the extension's actual 32-character ID. The Store update source is
`https://clients2.google.com/service/update2/crx`.

For a managed self-hosted route, sign/package the exact `extension/` contents and
publish the CRX and its HTTPS update-manifest XML. Keep the signing key: subsequent
versions must retain the same extension ID. The update manifest must identify the
correct ID, version and CRX URL. Chrome update requests cannot rely on the
operator's signed-in browser cookies. See Google's
[self-hosting instructions](https://developer.chrome.com/docs/extensions/how-to/distribute/host-on-linux).

Neither the ZIP nor an unpacked extension is a signed, installable CRX. The setup
app does not publish to the Store, sign an extension, or host an update service.

### 3. Reopen the prepared setup

Choose **Open prepared setup…** and select `setup.json` inside the prepared
folder, or use **Enter published ID…** while that bundle is still open. Keep the
entire folder together: reopening verifies its inventory, checksums, generated
rules and publication ZIP.

The school websites, access rules and extension version are now locked to that
package. Enter the real published ID and update source, confirm that you
published **this exact prepared extension**, then export the deployment into a
new folder. The publication and deployment ZIPs remain identical.

The fingerprint prevents accidental configuration drift. The publication
confirmation is the operator's statement; it does **not** prove that the remote
Store or update server actually serves those bytes.

### 4. Install the enterprise policy

Open the final deployment's `setup.json` on its target OS and follow the
**Install & verify** page. For centrally managed devices, apply the supplied
policy through the system that already owns Chrome policy.

| Platform | Installation route | Existing policy handling |
| --- | --- | --- |
| Windows | Choose **Install policy (administrator)** and approve Windows UAC. The result appears in the administrator action's window. | Adds the SchoolOps entry to the 64-bit HKLM `ExtensionSettings` value while preserving wildcard and unrelated extension entries. A conflicting SchoolOps entry is refused. Use the authoritative GPO/cloud console when it controls that value. |
| Linux, Google Chrome | Choose **Install policy (administrator)**. A desktop with `pkexec` shows its administrator prompt; otherwise the app copies a `sudo` command for a terminal. | Creates `/etc/opt/chrome/policies/managed/school-ops-youtube-guard.json`. It refuses another managed JSON file defining `ExtensionSettings`; merge through that policy's administrator instead. |
| macOS | Deploy `deployment/schoolops-chrome.mobileconfig` through your MDM as a computer-level profile. | The exported profile is unsigned. If Chrome already has an `ExtensionSettings` payload, merge the supplied value into that profile instead of installing a competing profile. |
| ChromeOS | In Google Admin, open **Devices → Chrome → Apps & extensions → Users & browsers**, select the intended organizational unit, add the extension by ID/update source, choose **Force install**, and save. | Configure the correct user/device scope in the existing Admin Console. The setup app does not enroll devices. |

A repeated Windows/Linux installation of an identical policy is a no-op. Policy
application records a machine-level ownership receipt only when this installer
adds the policy.

**Self-hosting prerequisites:** Windows requires Active Directory domain join,
Azure AD join, or Chrome Enterprise Core enrollment. macOS requires MDM
management, MCX domain membership, or Chrome Enterprise Core enrollment. A local
registry write or locally opened profile does not establish that enrollment.
These restrictions are specified in the
[current Chromium force-install policy](https://chromium.googlesource.com/chromium/src/+/HEAD/components/policy/resources/templates/policy_definitions/Extensions/ExtensionInstallForcelist.yaml).
Self-hosted exports include `override_update_url: true` so later extension
updates continue to use the supplied policy update source.

### 5. Verify in Chrome

Use the setup app's copy buttons to paste these addresses into Chrome:

1. **`chrome://policy`:** click **Reload policies**, confirm `ExtensionSettings`
   has **Status OK**, and check its extension ID and update source.
2. **`chrome://extensions`:** confirm the expected ID and version, managed
   installation status, and inability to disable/remove it as a standard user.
3. Open the approved school portal and test a real embedded YouTube video.
   Check that direct YouTube, “Watch on YouTube”/new-tab links, and YouTube embeds
   on an unapproved website are blocked.
4. Restart Chrome and repeat. Test the selected ordinary-site access rules too.

The app distinguishes a verified bundle, a local policy action, Chrome
installation, and website behavior. A successful export or policy write does not
mark Chrome installation or playback as verified.

## Updating or removing a deployment

**Change website rules:** reopen the previous setup, choose **New configuration**,
increase the extension version, and prepare/publish the new package under the
same extension ID and signing key. Reopen that new package to finalize its
policy. Rules are compiled into the extension's static ruleset; they are **not**
runtime `storage.managed` settings. Existing devices obtain changed rules through
the extension's publishing/update channel.

**Remove local policy:** reopen the deployment bundle used for installation and
choose **Remove local policy**. Windows/Linux removal requires the installer's
machine-level ownership receipt and an unchanged matching policy. It preserves other entries
and refuses to remove a pre-existing identical policy that this installer did
not create. If an administrator changed the entry, resolve that change through
its owner. Remove GPO/MDM/Admin Console policy in its management system. Check
Chrome afterward; removing local policy is not itself proof of extension removal.

## What is in a bundle?

| Artifact | Purpose |
| --- | --- |
| `extension/` | Configured MV3 manifest, static rules and administrator configuration |
| `extension.zip` | Deterministic publication ZIP of those exact extension files |
| `setup.json` | Saved settings and the extension ZIP fingerprint; reopen in Setup |
| `START_HERE.html` | Local, readable guide with the next action and verification steps |
| `deployment/README.md` | Platform-specific installation and recovery guidance |
| `SHA256SUMS.json` | SHA-256 inventory of generated files |
| `deployment/linux-managed-policy.json` | Complete Linux policy; generated after publication confirmation |
| `deployment/extension-settings-value.json` | Value to merge into an existing GPO/MDM `ExtensionSettings` policy |
| `deployment/schoolops-chrome.mobileconfig` | Unsigned macOS management profile; generated after publication confirmation |

The exporter never replaces an existing destination folder. Retain the original
prepared and deployment bundles privately if their school hostnames or internal
policy details should not be public.

## Development and acceptance

For an unpacked development pilot, generate a bundle and use **Load unpacked** in
`chrome://extensions` with its `extension/` folder. Such a developer installation
is removable and does not establish enterprise enforcement.

Chrome 145+ supplies the `excludedTopDomains` declarative-network-request
condition used to distinguish the top-level school website from the YouTube
iframe's initiator. The [browser acceptance harness](acceptance/README.md) checks
network enforcement against controlled HTTPS fixtures. Its hypothetical DNR
probes are reported separately. Neither result establishes real YouTube playback
or managed-device enforcement.

Windows assumes administrator-controlled HKLM policy and receipt keys. It
rechecks values before writing, but does not transact across simultaneous policy
writers or audit custom registry ACLs. Tests include disposable HKCU registry
operations; actual HKLM deployment and Chrome enforcement remain untested. Linux
checks root ownership, directory permissions and symlink-free policy ancestry.

Run the Python contracts from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

The [native workflow](../../../.github/workflows/youtube-guard-native.yml) builds
on Windows, macOS and Ubuntu. Its Linux UI smoke test exercises the graphical
flow under Xvfb. Each packaged `--self-test` verifies bundled data, draft export,
resumption and policy-bundle generation without changing system policy or
installing Chrome. Native build provenance and smoke results accompany each
artifact. To build a native candidate on the matching OS:

```sh
python -m pip install "pyinstaller==6.22.3"
python tools/browser/site_scoped_youtube_guard/package_native.py \
  --output-dir native-wizard-output
```

Before rollout, establish the actual approved hostnames, exact signed/published
extension, approved native-app distribution, real YouTube playback, and managed
standard-user installation. Browser controls cannot by themselves restrict
administrator access, alternate browsers/apps, proxies or unmanaged devices;
cover those through device controls where required.

### Official references

- [Chrome ExtensionSettings](https://support.google.com/chrome/a/answer/9867568)
- [Linux policy deployment and conflicting policy files](https://support.google.com/chrome/a/answer/9027408)
- [Automatically install Chrome apps and extensions](https://support.google.com/chrome/a/answer/6306504)
- [Extension distribution](https://developer.chrome.com/docs/extensions/how-to/distribute)
- [Chrome declarativeNetRequest API](https://developer.chrome.com/docs/extensions/reference/api/declarativeNetRequest)
