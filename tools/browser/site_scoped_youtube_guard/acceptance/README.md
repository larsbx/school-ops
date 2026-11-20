# Run the browser acceptance tests

Use Node 20+, Python 3 and OpenSSL. Run here:

```sh
npm ci --ignore-scripts
npx playwright-core install --with-deps chromium
npm test
```

1. **Read the run.** Open `artifacts/report.json` or set
   `GUARD_EVIDENCE_DIR` to a fresh directory. Check the browser version, source
   revision, fixture responses and server hits.
2. **Review both results.** `browserNetwork` records controlled HTTPS requests
   with no extension and with each filtering mode. `hypotheticalDnr` records
   Chrome's simulated matches.
3. **Verify rollout on a managed standard-user device.** Test real playback,
   blocked navigation and force-install after applying the published build.
   [Device checks](../README.md)

[Harness options and assertions](../.llm.txt)
