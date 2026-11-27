# Read-only local policy check

The native and Python setup wizard has a **Check local policy (read-only)**
action on its final **Install & verify** page. This closes a limited observation
gap: the app can distinguish a matching, absent, different, conflicting, or
uninspectable local policy from the state of the *expected reviewed bundle*.

**It does not verify Chrome is using the policy.** A matching local file or
registry entry is not proof that the extension was installed, locked, or that
YouTube embeds work. This operation does not elevate privileges, install,
remove, enroll, modify, or restart anything.

## Operate

1. Open a previously prepared **published** deployment with the installer.
   The saved bundle must pass exact-file checksum, extension ID, rules, version
   and publication requirements. An unpublished draft cannot be checked.
2. On the final page choose **Check local policy (read-only)**. It does not
   request the administrator password.
3. Read the result, then complete the separate Chrome checks below.

Alternatively run the source CLI on the device:

```sh
python3 tools/browser/site_scoped_youtube_guard/device_check.py /path/to/published-bundle
python3 tools/browser/site_scoped_youtube_guard/device_check.py /path/to/published-bundle \
  --report /path/to/new-local-observation.json
```

The packaged native setup also supports `--check-policy /path/to/bundle`.
CLI exit codes: `0` means a matching **local** policy was observed; `1`
means the observation was not a match or was unsupported; `2` means a bad
bundle, report-output conflict or another safe failure. Never treat exit 0 as
the school's production rollout acceptance signal.

The JSON report identifies a public extension ID, expected policy hash,
target/observed OS, timestamp and scoped outcome, but not the school hostname,
device identity or user profile. Only create a report when needed, in a
private administrator-controlled destination; existing files are never
overwritten.

## What is inspected

| OS | Read-only scope | Limit |
| --- | --- | --- |
| Windows | 64-bit HKLM Chrome `ExtensionSettings` registry value | GPO/cloud policy precedence or Chrome's effective view may differ |
| Linux (Google Chrome) | All `*.json` files in the root-managed Chrome policy directory, with symlink/owner/size protections | Another `ExtensionSettings` file yields `conflicting`, not a guessed precedence |
| macOS | No local inspection in this version | MDM/managed preference state needs separate trusted observation |
| ChromeOS | No local inspection in this version | Chrome Admin / OS policy must be checked in the management console and Chrome |

Unreadable, malformed, ambiguous or changed snapshots **never** become a
passing match. The local check does not read or modify Chrome profiles or
students' personal data, perform network requests, or access any private
signing key. The comparison is point-in-time and does not prove policy
durability or absence of higher-priority cloud policy.

## Required additional acceptance

On a managed school device signed in as a **standard user**, inspect
`chrome://policy` after **Reload policies** and verify `ExtensionSettings`
reports OK with the expected ID, version and source. Confirm the extension
appears in `chrome://extensions`, cannot be disabled/uninstalled, survives
restart, and receives its intended version. Then test a real embedded YouTube
video on the approved school site, direct YouTube and Watch-on-YouTube links,
and embeds from unauthorized websites. Record failures and distinguish those
checks from local registry/file matching.

For centrally managed GPO/MDM devices, reconcile policy with their actual
administrator; this utility cannot override or certify that authority.
The parent production acceptance checklist remains
[SchoolOps issue #24](https://github.com/larsbx/school-ops/issues/24).
