#!/usr/bin/env node
// Actual browser network enforcement over local HTTPS, plus separately labelled
// hypothetical DNR probes. No Playwright routing, real YouTube, or managed policy.
const assert = require('node:assert/strict');
const { createHash, generateKeyPairSync, randomUUID } = require('node:crypto');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const https = require('node:https');
const os = require('node:os');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const output = path.resolve(process.env.GUARD_EVIDENCE_DIR || path.join(__dirname, 'artifacts'));
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'schoolops-acceptance-'));
const report = {
  schema: 1, startedAt: new Date().toISOString(), status: 'failed',
  scope: 'Unpacked MV3 static rules; controlled HTTPS responses, not YouTube playback',
  realYouTubePlayback: 'not_run', signedPublication: 'not_tested', managedEnforcement: 'not_tested',
  browserNetwork: [], hypotheticalDnr: [], serverRequests: [],
};
let server;
let context;
let outputReady = false;
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const json = (name, value) => fs.writeFileSync(path.join(output, name), JSON.stringify(value, null, 2) + '\n');
const config = mode => ({
  allowed_embed_sites: ['school.test'], allowed_sites: ['library.test'],
  blocked_sites: ['blocked.test'], mode,
});
// Only a public test key is added to a COPY of the manifest to locate the
// extension probe. No extra permissions, worker, dynamic rules, or production edits.
const publicKey = generateKeyPairSync('rsa', { modulusLength: 2048 }).publicKey
  .export({ type: 'spki', format: 'der' });
const extensionId = createHash('sha256').update(publicKey).digest('hex').slice(0, 32)
  .replace(/[0-9a-f]/g, c => String.fromCharCode(97 + parseInt(c, 16)));

async function until(fn, label) {
  const deadline = Date.now() + 8000;
  while (Date.now() < deadline) {
    const value = fn();
    if (value) return value;
    await new Promise(resolve => setTimeout(resolve, 20));
  }
  throw new Error(`Timed out: ${label}`);
}

async function run() {
  // Never mix stale output with evidence from this execution.
  fs.mkdirSync(output, { recursive: true });
  assert.equal(fs.readdirSync(output).length, 0, 'Use an empty GUARD_EVIDENCE_DIR');
  outputReady = true;
  const { chromium } = require('playwright-core');
  report.playwrightVersion = require('playwright-core/package.json').version;
  report.platform = { os: os.platform(), release: os.release(), arch: os.arch(), node: process.version };
  report.source = {
    commit: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    dirty: !!execFileSync('git', ['status', '--porcelain'], { cwd: root, encoding: 'utf8' }).trim(),
    generatorSha256: hash(fs.readFileSync(path.join(root, 'build_rules.py'))),
    harnessSha256: hash(fs.readFileSync(__filename)),
    manifestSha256: hash(fs.readFileSync(path.join(root, 'manifest.json'))),
  };
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
    '-subj', '/CN=schoolops-fixtures', '-keyout', path.join(temporary, 'tls.key'),
    '-out', path.join(temporary, 'tls.crt')], { stdio: 'ignore' });
  server = https.createServer({ key: fs.readFileSync(path.join(temporary, 'tls.key')),
    cert: fs.readFileSync(path.join(temporary, 'tls.crt')) }, (req, res) => {
    report.serverRequests.push({ host: req.headers.host, path: req.url, method: req.method });
    const pathname = new URL(req.url, 'https://fixture').pathname;
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('X-SchoolOps-Fixture', 'controlled-response');
    if (pathname.endsWith('.js')) {
      res.setHeader('Content-Type', 'application/javascript');
      res.end('globalThis.schoolopsFixtureScript = true;');
    } else if (pathname.endsWith('.gif')) {
      res.setHeader('Content-Type', 'image/gif');
      res.end(Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64'));
    } else {
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.end('<!doctype html><title>SchoolOps controlled fixture</title><body>Controlled fixture</body>');
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  const url = (host, suffix = '') => `https://${host}:${port}/case-${randomUUID()}${suffix}`;
  const args = ['--host-resolver-rules=MAP * 127.0.0.1, EXCLUDE localhost',
    '--no-proxy-server', '--ignore-certificate-errors', '--disable-quic'];
  if (process.env.GUARD_NO_SANDBOX === '1') args.push('--no-sandbox');
  report.launch = { channel: 'chromium', headless: process.env.GUARD_HEADED !== '1',
    executablePath: process.env.CHROME_EXECUTABLE || chromium.executablePath(), args };
  report.fixture = { scheme: 'https', address: '127.0.0.1', port,
    dns: 'All fixture hosts resolve to loopback; browser proxy disabled; self-signed test certificate trusted via flag' };

  for (const mode of ['control', 'blacklist', 'whitelist']) {
    const extension = path.join(temporary, mode);
    fs.mkdirSync(extension);
    const manifest = JSON.parse(fs.readFileSync(path.join(root, 'manifest.json')));
    manifest.key = publicKey.toString('base64');
    const cfg = config(mode === 'control' ? 'blacklist' : mode);
    const rules = JSON.parse(execFileSync(process.env.PYTHON || 'python3', ['-c',
      'import json,sys; from build_rules import build; print(json.dumps(build(json.loads(sys.argv[1]))))',
      JSON.stringify(cfg)], { cwd: root, encoding: 'utf8' }));
    fs.writeFileSync(path.join(extension, 'manifest.json'), JSON.stringify(manifest));
    fs.writeFileSync(path.join(extension, 'rules.json'), JSON.stringify(rules));
    fs.writeFileSync(path.join(extension, 'probe.html'), '<!doctype html><title>DNR probe</title>');
    if (mode !== 'control') {
      json(`${mode}-config.json`, cfg);
      json(`${mode}-rules.json`, rules);
      json(`${mode}-test-manifest.json`, manifest);
    }
    context = await chromium.launchPersistentContext(path.join(temporary, `profile-${mode}`), {
      channel: 'chromium', headless: report.launch.headless,
      ...(process.env.CHROME_EXECUTABLE ? { executablePath: process.env.CHROME_EXECUTABLE } : {}),
      args: mode === 'control' ? args : [...args, `--disable-extensions-except=${extension}`, `--load-extension=${extension}`],
      ignoreHTTPSErrors: true, serviceWorkers: 'block',
    });
    const version = context.browser().version();
    report.browserVersion = version;
    assert.ok(Number(version.split('.')[0]) >= 145, `Chrome 145+ required; got ${version}`);
    const network = [];
    context.on('response', response => network.push({ url: response.url(), status: response.status(),
      fixture: response.headers()['x-schoolops-fixture'], resourceType: response.request().resourceType() }));
    context.on('requestfailed', request => network.push({ url: request.url(),
      error: request.failure().errorText, resourceType: request.resourceType() }));

    // A startup probe fails if the extension is absent or its static rules did not
    // load. These API results are hypothetical, never counted as network tests.
    if (mode !== 'control') {
      const probe = await context.newPage();
      await probe.goto(`chrome-extension://${extensionId}/probe.html`);
      const enabled = await probe.evaluate(() => chrome.declarativeNetRequest.getEnabledRulesets());
      assert.deepEqual(enabled, ['site_guard_rules']);
      for (const top of ['school.test', 'child.school.test', 'library.test', 'school.test.evil.test']) {
        const request = { url: url('www.youtube.com'), topUrl: url(top),
          initiator: url('www.youtube.com'), type: 'sub_frame' };
        const actual = await probe.evaluate(req => chrome.declarativeNetRequest.testMatchOutcome(req), request);
        const expected = top === 'school.test' || top === 'child.school.test' ? [] : [2];
        const entry = { mode, request, expectedRuleIds: expected, actual, passed: false };
        report.hypotheticalDnr.push(entry);
        assert.deepEqual(actual.matchedRules.map(rule => rule.ruleId), expected);
        entry.passed = true;
      }
      await probe.close();
    }

    async function check(name, target, expectedBlocked, trigger) {
      const entry = { mode, name, target, expected: mode === 'control' ? 'allowed' :
        expectedBlocked ? 'blocked' : 'allowed', passed: false };
      report.browserNetwork.push(entry);
      const index = network.length;
      const serverIndex = report.serverRequests.length;
      try {
        await trigger();
        entry.observed = await until(() => network.slice(index).find(event => event.url === target), name);
        entry.serverHits = report.serverRequests.slice(serverIndex).filter(req =>
          `https://${req.host}${req.path}` === target).length;
        if (entry.expected === 'blocked') {
          assert.equal(entry.observed.error, 'net::ERR_BLOCKED_BY_CLIENT');
          assert.equal(entry.serverHits, 0, 'Blocked request reached fixture server');
        } else {
          assert.equal(entry.observed.status, 200);
          assert.equal(entry.observed.fixture, 'controlled-response');
          assert.equal(entry.serverHits, 1);
        }
        entry.passed = true;
      } catch (error) {
        entry.error = error.stack;
        console.error(`${mode}: ${name}: ${error.message}`);
      }
    }
    async function navigate(name, host, blocked, suffix = '') {
      const page = await context.newPage();
      const target = url(host, suffix);
      try { await check(name, target, blocked, () => page.goto(target).catch(error => {
        // Assert the network outcome below; never reinterpret a timeout or DNS
        // error as an extension block.
        if (!error.message.includes('net::ERR_BLOCKED_BY_CLIENT')) throw error;
      })); } finally { await page.close(); }
    }
    for (const host of ['youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be',
      'youtube-nocookie.com', 'www.youtube-nocookie.com', 'youtube.com.']) {
      await navigate(`standalone ${host}`, host, true);
      await navigate(`standalone embed path ${host}`, host, true, '/embed/video');
    }
    for (const host of ['school.test', 'child.school.test', 'library.test', 'child.library.test',
      'blocked.test', 'child.blocked.test', 'ordinary.test', 'notschool.test', 'school.test.evil.test',
      'youtube.com.evil.test']) {
      const blocked = host === 'blocked.test' || host === 'child.blocked.test' ||
        (mode === 'whitelist' && !['school.test', 'child.school.test', 'library.test', 'child.library.test'].includes(host));
      await navigate(`website filter ${host}`, host, blocked);
    }
    // library.test is allowed as an ordinary website in BOTH modes, but is not
    // an approved embedding site. This tests embeds without a whitelist confound.
    for (const top of ['school.test', 'child.school.test', 'library.test']) {
      const page = await context.newPage();
      await page.goto(url(top));
      const blocked = top === 'library.test';
      for (const host of ['www.youtube.com', 'm.youtube.com', 'www.youtube-nocookie.com', 'youtu.be']) {
        const target = url(host, '/embed/video');
        await check(`iframe ${host} under ${top}`, target, blocked, () => page.evaluate(src => {
          const frame = document.createElement('iframe'); frame.src = src; document.body.append(frame);
        }, target));
      }
      // Navigate an already loaded neutral iframe, rather than only inserting one.
      const frameElement = await page.evaluateHandle(() => {
        const frame = document.createElement('iframe'); document.body.append(frame); return frame;
      });
      const target = url('www.youtube.com', '/embed/navigated');
      await check(`iframe navigation under ${top}`, target, blocked,
        () => frameElement.evaluate((frame, src) => { frame.src = src; }, target));
      // A user-clicked target=_blank link models "Watch on YouTube".
      const popupUrl = url('www.youtube.com', '/watch');
      await page.evaluate(href => { const link = document.createElement('a');
        link.id = 'watch'; link.target = '_blank'; link.href = href; link.textContent = 'Watch';
        document.body.append(link); }, popupUrl);
      await check(`new tab from ${top}`, popupUrl, true, async () => {
        const popup = context.waitForEvent('page'); await page.locator('#watch').click(); await popup;
      });
      await page.close();
      for (const popup of context.pages()) await popup.close();
    }
    // Intermediate-frame origin must not confer approval on an unapproved top.
    // Conversely, an intermediate third party does not remove top-site approval.
    for (const [top, middle, blocked] of [['library.test', 'school.test', true],
      ['school.test', 'ordinary.test', false], ['library.test', 'school.test.evil.test', true]]) {
      const page = await context.newPage();
      await page.goto(url(top));
      const middleUrl = url(middle);
      await page.evaluate(src => { const frame = document.createElement('iframe');
        frame.src = src; document.body.append(frame); }, middleUrl);
      await until(() => page.frames().find(frame => frame.url() === middleUrl), 'middle frame');
      const frame = page.frames().find(frame => frame.url() === middleUrl);
      await frame.waitForLoadState();
      const target = url('www.youtube.com', '/embed/nested');
      await check(`nested iframe ${top} > ${middle}`, target, blocked, () => frame.evaluate(src => {
        const child = document.createElement('iframe'); child.src = src; document.body.append(child);
      }, target));
      await page.close();
    }
    // Check suffix-boundary lookalikes as top-level frame hosts in blacklist mode;
    // whitelist correctly denies these top-level pages before they can embed.
    if (mode !== 'whitelist') for (const top of ['notschool.test', 'school.test.evil.test']) {
      const page = await context.newPage(); await page.goto(url(top));
      const target = url('www.youtube.com', '/embed/lookalike');
      await check(`lookalike top ${top}`, target, true, () => page.evaluate(src => {
        const f = document.createElement('iframe'); f.src = src; document.body.append(f);
      }, target));
      await page.close();
    }
    for (const top of ['school.test', 'library.test']) {
      const page = await context.newPage(); await page.goto(url(top));
      for (const [host, kind, suffix] of [['i.ytimg.com', 'image', '.gif'],
        ['youtubei.googleapis.com', 'script', '.js'], ['youtube.googleapis.com', 'fetch', ''],
        ['rr1.googlevideo.com', 'fetch', '']]) {
        const target = url(host, suffix);
        await check(`${kind} ${host} under ${top}`, target, top === 'library.test', () => page.evaluate(({ src, kind }) => {
          if (kind === 'fetch') { fetch(src).catch(() => {}); return; }
          const element = document.createElement(kind === 'image' ? 'img' : 'script');
          element.src = src; document.body.append(element);
        }, { src: target, kind }));
      }
      await page.close();
    }
    await context.close(); context = undefined;
  }
  const failures = report.browserNetwork.filter(entry => !entry.passed);
  assert.equal(failures.length, 0, `${failures.length} browser network cases failed`);
  report.status = 'passed';
}

run().catch(error => { report.error = error.stack; process.exitCode = 1; }).finally(async () => {
  if (context) await context.close().catch(() => {});
  if (server) await new Promise(resolve => server.close(resolve));
  fs.rmSync(temporary, { recursive: true, force: true });
  report.finishedAt = new Date().toISOString();
  // If output was already populated, preserve it and refuse to overwrite.
  if (outputReady) {
    fs.mkdirSync(output, { recursive: true }); json('report.json', report);
  }
  if (report.error) console.error(report.error);
  console.log(`${report.status}: ${report.browserNetwork.filter(x => x.passed).length}/${report.browserNetwork.length} network cases; ` +
    `${report.hypotheticalDnr.filter(x => x.passed).length}/${report.hypotheticalDnr.length} separate hypothetical probes; ${output}`);
});
