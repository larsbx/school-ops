# Set up the SchoolOps YouTube Guard

Use Chrome 145+ to allow YouTube embeds on approved portals and block
standalone YouTube. Production signing, publication and managed rollout are pending.

1. **Open Setup.** Download your OS artifact from a successful build for the
   intended revision. Check its commit, architecture and SHA-256. Extract and
   keep the entire app together. Use an organization-approved signed build
   for rollout. CI builds are unsigned.
   [Native builds](https://github.com/larsbx/school-ops/actions/workflows/youtube-guard-native.yml)
2. **Prepare.** Enter actual portal hostnames, one per line. Each includes its
   subdomains. Blacklist blocks listed sites. Whitelist limits top-level
   browsing to approved and additional allowed sites. Select the OS and
   channel, leave the extension ID blank and export to a new folder. Open
   `START_HERE.html` in that folder for the next step.
3. **Publish.** Upload the exact `extension.zip` to the Chrome Web Store. Reopen
   `setup.json`, enter the published ID, confirm the package and export.
   For managed self-hosting, sign and verify the published bytes before export.
   [Self-hosted release](RELEASE.md)
4. **Install.** Reopen the deployment's `setup.json`. Apply policy through
   the system that already manages Chrome. Merge with existing
   `ExtensionSettings` through that policy's owner.

   | Platform | Action |
   | --- | --- |
   | Windows / Linux | Choose **Install policy (administrator)** for local policy. |
   | macOS | Deploy `deployment/schoolops-chrome.mobileconfig` through MDM. |
   | ChromeOS | Open **Devices → Chrome → Apps & extensions → Users & browsers** in Google Admin. Select the organizational unit, add the ID and update source, choose **Force install**, and save. |

5. **Verify as a standard user.** Reload `chrome://policy` and check
   `ExtensionSettings`. In `chrome://extensions`, confirm the ID, version
   and managed status. Check that users cannot disable or remove the extension.
   Play a real portal embed. Check that direct YouTube, new tabs and off-portal
   embeds are blocked. Repeat after restart and check the selected site rules.

**Update** via **New configuration**. Increase the version and publish with the
same extension ID and key. **Remove** local policy from its original deployment
bundle. Local removal requires an unchanged policy and its installer receipt.
Remove centrally managed policy through its management console.

To run Setup from the checkout, use Python with Tkinter:

```sh
python3 tools/browser/site_scoped_youtube_guard/wizard.py
```

[Browser tests](acceptance/README.md) · [Agent and development reference](.llm.txt)
