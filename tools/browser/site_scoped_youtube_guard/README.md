# Site-Scoped YouTube Guard (Chrome 145+, MV3)

This is a SchoolOps **device/browser policy utility**, not a curriculum record or a
biz-kit authorization mechanism. It allows YouTube **embeds on approved top-level
websites**, while preventing users from opening YouTube as a standalone site.

**Status: prototype.** Not published, deployed, or browser-tested on a managed
school device. The default approved hostname is a reserved `.invalid` placeholder:
**no actual school website is approved yet**.

## Configure and test

1. Replace `approved-site.invalid` in `config.json` with the school portal
   hostname (e.g. `portal.example.org`). Use a hostname, not a URL or wildcard.
   Chrome matches subdomains as well.
2. Choose `mode`: `blacklist` permits ordinary websites except
   `blocked_sites`; `whitelist` blocks all ordinary top-level websites except
   `allowed_sites` and `allowed_embed_sites`. Direct YouTube navigation
   is blocked in **both** modes.
3. Run `python3 build_rules.py` and review the generated `rules.json`.
   Configuration and generated rules must be reviewed together.
4. For **development only**, open `chrome://extensions`, enable Developer
   mode and use *Load unpacked* with this directory. An unpacked extension is
   removable and **not tamper-resistant**.

Verify these cases in Chrome 145+:
- Embedded YouTube video plays in the approved school portal.
- Direct `youtube.com`, `m.youtube.com`, `youtu.be` and
  `youtube-nocookie.com` navigation is blocked from any tab.
- "Watch on YouTube" from an embedded player cannot open the main site.
- YouTube embeds from a non-approved website are blocked.
- Blacklist and whitelist mode produce the expected non-YouTube browsing rules.
- Domain variants, iframe navigation and new tabs do not bypass restrictions.

Chrome 145+ provides the `excludedTopDomains` DNR condition used to distinguish
top-level site context from YouTube iframe initiators. A basic
`initiatorDomains` condition does **not** reliably provide that distinction.

Tests: from the repository root run
`python -m unittest discover -s tests -v`.
These are rule-generation contract tests only; Chrome behavior needs separate
browser tests. With Chrome 145+, `chrome.declarativeNetRequest.testMatchOutcome`
can help test `topUrl`, but it does not replace actual playback testing.

## Administrator enforcement and threat model

To prevent removal or reconfiguration, publish/package the extension through a
supported channel and use managed Chrome `ExtensionSettings` with
`installation_mode: force_installed`, a real extension ID, and its valid
`update_url`. Device users must have standard (non-administrator) OS accounts.
An admin-controlled device management policy, rather than a password hardcoded
in JavaScript, protects rule changes.

Example policy **only after publication**, using the real ID and correct channel:

```json
{
  "ACTUAL_32_CHARACTER_EXTENSION_ID": {
    "installation_mode": "force_installed",
    "update_url": "https://clients2.google.com/service/update2/crx"
  }
}
```

The Web Store update URL applies **only** when the extension is genuinely
published there. Unpacked developer installs do not provide enforcement.
A Windows/macOS/Linux managed deployment may use different packaging and
administrative configuration.

**Limitations:** Other browsers, apps, proxy websites, administrator access,
unmanaged devices or networks may bypass browser-only controls. Restrict them
using system policies where needed. Video embeds depend on the hosting site's
implementation and YouTube's hosts; playback must be tested after configuration.
Direct links out to YouTube are intentionally blocked even from the school site.
A global Chrome URL blocklist alone would also block embedded players; this
extension enforces resource context.

## Acceptance gates (not yet satisfied)

- [ ] Actual approved school hostname provided; placeholder removed.
- [ ] Generated rules reviewed, committed, and verified in Chrome 145+.
- [ ] Real YouTube playback succeeds only on approved portal(s).
- [ ] Standalone, new-tab and off-site YouTube playback attempts fail.
- [ ] Extension is genuinely force-installed and cannot be disabled or removed
      on managed standard-user devices.
- [ ] Alternative-browser/app bypass covered by device controls if in scope.

References:
- https://developer.chrome.com/docs/extensions/reference/api/declarativeNetRequest
- https://support.google.com/chrome/a/answer/9867568
