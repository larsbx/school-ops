# Publish a managed self-hosted release

Use Python 3.11+ for source commands and OpenSSL 3 for signing and verification.
Confirm enrollment before publishing. Windows self-hosting requires Active
Directory, Azure AD, or Chrome Enterprise Core enrollment. macOS requires MDM,
MCX, or Chrome Enterprise Core enrollment. [Release requirements](.llm.txt)

1. **Prepare.** Open a saved self-hosted `setup.json`. Choose **Prepare
   self-hosted release…**. Supply the public RSA key, pinned extension ID,
   exact version, stable HTTPS update URL and versioned CRX URL on the same
   origin. Select the previous signed release or declare the first release.
2. **Sign.** Have the authorized signer run the copied command. With an
   external signer, sign `signing-input.bin` with RSA PKCS#1 v1.5 and SHA-256,
   then run `python release_core.py assemble release/ --signature signature.bin`.
   Keep private keys in the signing environment.
3. **Review.** Check the ID, version, destinations, hashes and predecessor.
   For local staging, run from this directory:

   ```sh
   python release_core.py plan-stage release/ staging-root/
   python release_core.py stage release/ staging-root/ --approve-plan-sha256 APPROVED_PLAN_SHA256
   ```

   Run the second command with the hash from the approved plan. After approval
   for remote publication, upload `extension.crx` first and activate
   `update.xml` last. Serve both over HTTPS with anonymous access. Use
   `application/x-chrome-extension` for the CRX and `application/xml` or
   `text/xml` for the manifest.
4. **Verify and export.** Choose **Verify HTTPS & export…**, select the signed
   release, and choose a new deployment folder. The receipt records the bytes
   observed during verification. Verify installation and playback on the target
   device. [Setup guide](README.md)
5. **Update.** Keep the same key, ID and update URL. Use a higher version, a new
   CRX URL and the previous signed release.

**Recover an interrupted stage.** Rebuild the plan and retry. Inspect any
package or predecessor conflict before proceeding.

[CLI examples, recovery details and verification scope](.llm.txt)
