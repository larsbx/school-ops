#!/usr/bin/env python3
"""Batched, resumable, polite archive of a website, tracked by a TSV manifest.

The manifest (committed to the repo) holds metadata only: one row per discovered
URL with its status. Downloaded files live outside the repo in --archive and are
optionally copied to an rclone remote. Any session can continue from the manifest.

Fetchable: the site itself, plus archive.org items (expanded via the metadata API
into their original files) and archive.org file downloads it links to.

Status: pending | fetched (local copy only) | stored (on remote) | indexed
(archive.org item expanded into file rows) | failed:<why> | external
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

HOST = "www.arvindguptatoys.com"
IA = "archive.org"
HOSTS = {"arvindguptatoys.com": HOST, HOST: HOST, "www.archive.org": IA, IA: IA}
IA_SKIP_FORMATS = {"Metadata", "Item Tile", "Archive BitTorrent"}
SEED = f"https://{HOST}/"
FIELDS = ("url", "status", "content_type", "bytes", "sha256", "fetched_at", "title", "found_on")
UA = "school-ops-archive/1.0 (polite; honours robots.txt crawl-delay)"
LINK_ATTRS = {"a": "href", "link": "href", "img": "src", "iframe": "src", "embed": "src", "source": "src"}


# ---- pure helpers -----------------------------------------------------------

def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def canonical(href, base):
    """Absolute, fragment-free, consistently quoted URL; None if not http(s)."""
    href = (href or "").strip()
    if not href or href.startswith("#"):
        return None
    parts = urlsplit(urljoin(base, href))
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    host = parts.netloc.lower()
    scheme, host = ("https", HOSTS[host]) if host in HOSTS else (parts.scheme, host)
    path = quote(unquote(parts.path) or "/", safe="/:@!$&'()*+,;=~-._")
    return urlunsplit((scheme, host, path, parts.query, ""))


def is_internal(url):
    return urlsplit(url).netloc == HOST


def _ia_path(url):
    parts = urlsplit(url)
    return [s for s in parts.path.split("/") if s] if parts.netloc == IA else []


def ia_item(url):
    """Item id for an archive.org item page (details/<id>/... or download/<id>/), else None."""
    segs = _ia_path(url)
    is_item = segs[:1] == ["details"] or (segs[:1] == ["download"] and len(segs) == 2)
    return unquote(segs[1]) if is_item and len(segs) > 1 else None


def fetchable(url):
    segs = _ia_path(url)
    return is_internal(url) or bool(ia_item(url)) or (segs[:1] == ["download"] and len(segs) > 2)


def order(url):
    return (not is_internal(url), url)


def ia_originals(meta):
    return [f for f in meta.get("files", [])
            if f.get("source") == "original" and f.get("format") not in IA_SKIP_FORMATS]


def ia_files(item, meta):
    """Download URLs (with item title) for an item's original, non-bookkeeping files."""
    title = clean(str(meta.get("metadata", {}).get("title", "")))
    return [(f"https://{IA}/download/{quote(item)}/{quote(f['name'])}", title) for f in ia_originals(meta)]


def local_path(root, url):
    parts = urlsplit(url)
    segs = [s for s in unquote(parts.path).split("/") if s not in ("", ".", "..")]
    if parts.path.endswith("/") or not segs:
        segs.append("index.html")
    if parts.query:
        segs[-1] += "?" + parts.query.replace("/", "%2F")
    return Path(root, parts.netloc, *segs)


class _LinkParser(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.links, self._open = base, [], None

    def handle_starttag(self, tag, attrs):
        attr = LINK_ATTRS.get(tag)
        url = attr and canonical(dict(attrs).get(attr), self.base)
        if url:
            self.links.append([url, ""])
            self._open = self.links[-1] if tag == "a" else None

    def handle_data(self, data):
        if self._open is not None:
            self._open[1] += data

    def handle_endtag(self, tag):
        if tag == "a":
            self._open = None


def extract_links(html, base):
    p = _LinkParser(base)
    p.feed(html)
    return [(u, clean(t)) for u, t in p.links]


def row(url, **kw):
    return {**dict.fromkeys(FIELDS, ""), "url": url, **kw}


def discover(rows, links, found_on):
    """New manifest with unseen links added (first title / referrer wins)."""
    new = {}
    for url, title in links:
        if url not in rows and url not in new:
            new[url] = row(url, status="pending" if fetchable(url) else "external",
                           title=clean(title), found_on=found_on)
    return {**rows, **new}


def reconcile(rows, root, retry_failed):
    """Requeue lost local-only copies (new container), newly fetchable externals,
    and, optionally, failures."""
    def requeue(r):
        lost = r["status"] == "fetched" and not local_path(root, r["url"]).is_file()
        promoted = r["status"] == "external" and fetchable(r["url"])
        failed = retry_failed and r["status"].startswith("failed")
        return {**r, "status": "pending"} if lost or promoted or failed else r
    return {u: requeue(r) for u, r in rows.items()}


def load(path):
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    return {r["url"]: r for r in (dict(zip(FIELDS, l.split("\t"))) for l in lines[1:] if l)}


def save(path, rows):
    tmp = path.with_suffix(".tmp")
    body = ["\t".join(FIELDS)] + ["\t".join(clean(str(rows[u][f])) for f in FIELDS) for u in sorted(rows)]
    tmp.write_text("\n".join(body) + "\n", encoding="utf-8")
    tmp.replace(path)


# ---- effects ----------------------------------------------------------------

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, dest):
    """Stream url to dest; return (row fields, html text or None)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            ctype = resp.headers.get_content_type()
            dest.parent.mkdir(parents=True, exist_ok=True)
            h, part = hashlib.sha256(), dest.with_name(dest.name + ".part")
            with open(part, "wb") as out:
                while chunk := resp.read(1 << 20):
                    h.update(chunk)
                    out.write(chunk)
            part.replace(dest)
            charset = resp.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as e:
        return {"status": f"failed:{e.code}"}, None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {"status": f"failed:{type(e).__name__}"}, None
    fields = {"status": "fetched", "content_type": ctype, "bytes": dest.stat().st_size,
              "sha256": h.hexdigest(), "fetched_at": now()}
    html = dest.read_text(encoding=charset, errors="replace") if ctype == "text/html" else None
    return fields, html


def expand(url, title):
    """Fetch an archive.org item's metadata; return (row fields, file links)."""
    item = ia_item(url)
    req = urllib.request.Request(f"https://{IA}/metadata/{quote(item)}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            meta = json.load(resp)
    except urllib.error.HTTPError as e:
        return {"status": f"failed:{e.code}"}, []
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        return {"status": f"failed:{type(e).__name__}"}, []
    if not meta:
        return {"status": "failed:no-item"}, []
    links, info = ia_files(item, meta), meta.get("metadata", {})
    return {"status": "indexed", "content_type": f"ia-item/{info.get('mediatype', '')}",
            "bytes": sum(int(f.get("size") or 0) for f in ia_originals(meta)),
            "fetched_at": now(), "title": title or clean(str(info.get("title", "")))}, links


def rclone_store(root, remote, urls):
    rels = [str(local_path(root, u).relative_to(root)) for u in urls]
    listing = Path(root, ".batch-files")
    listing.write_text("\n".join(rels) + "\n", encoding="utf-8")
    ok = subprocess.run(["rclone", "copy", str(root), remote, "--files-from", str(listing)]).returncode == 0
    return set(urls) if ok else set()


def git_commit(paths, message, push):
    subprocess.run(["git", "add", *map(str, paths)], check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        return
    subprocess.run(["git", "commit", "-q", "-m", message], check=True)
    for wait in (0, 2, 4, 8, 16) if push else ():
        time.sleep(wait)
        if subprocess.run(["git", "push", "-q", "-u", "origin", "HEAD"]).returncode == 0:
            return
    if push:
        print("warning: push failed; commit is local", file=sys.stderr)


class Polite:
    """Per-host robots.txt rules and minimum spacing between requests."""

    def __init__(self, delays):
        self.delays, self.rules, self.last = delays, {}, {}

    def _rules(self, host):
        if host not in self.rules:
            rp = urllib.robotparser.RobotFileParser(f"https://{host}/robots.txt")
            try:
                rp.read()
            except (urllib.error.URLError, OSError):
                rp.parse([])
            self.rules[host] = rp
        return self.rules[host]

    def allowed(self, url):
        return self._rules(urlsplit(url).netloc).can_fetch(UA, url)

    def wait(self, url):
        host = urlsplit(url).netloc
        delay = max(self.delays.get(host, max(self.delays.values())), float(self._rules(host).crawl_delay(UA) or 0))
        time.sleep(max(0.0, self.last.get(host, 0.0) + delay - time.monotonic()))
        self.last[host] = time.monotonic()


def disk_low(root, min_free_gb):
    return shutil.disk_usage(root).free < min_free_gb * 2**30


def run_batch(n, rows, args, polite):
    todo = [u for u in sorted(rows, key=order) if rows[u]["status"] == "pending"][: args.batch_size]
    started, fetched, attempted = now(), [], []
    for i, url in enumerate(todo):
        if disk_low(args.archive, args.min_free_gb):
            print(f"stopping: under {args.min_free_gb} GB free in {args.archive}", flush=True)
            break
        attempted.append(url)
        if not polite.allowed(url):
            rows = {**rows, url: {**rows[url], "status": "failed:robots"}}
            continue
        polite.wait(url)
        if ia_item(url):
            fields, links = expand(url, rows[url]["title"])
            rows = discover({**rows, url: {**rows[url], **fields}}, links, found_on=url)
        else:
            fields, html = fetch(url, local_path(args.archive, url))
            rows = {**rows, url: {**rows[url], **fields}}
            if html is not None and is_internal(url):
                rows = discover(rows, extract_links(html, url), found_on=url)
        if fields["status"] == "fetched":
            fetched.append(url)
        print(f"[{n}:{i + 1}/{len(todo)}] {fields['status']:<14} {url}", flush=True)
    stored = rclone_store(args.archive, args.remote, fetched) if args.remote and fetched else set()
    rows = {u: ({**r, "status": "stored"} if u in stored else r) for u, r in rows.items()}
    if args.prune_stored:
        for u in stored:
            local_path(args.archive, u).unlink(missing_ok=True)
    stats = {"batch": n, "started": started, "ended": now(), "attempted": len(attempted),
             "fetched": len(fetched), "stored": len(stored),
             "failed": sum(rows[u]["status"].startswith("failed") for u in attempted),
             "bytes": sum(int(rows[u]["bytes"] or 0) for u in fetched),
             "pending_after": sum(r["status"] == "pending" for r in rows.values()), "known": len(rows)}
    return rows, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    here = Path(__file__).resolve().parent.parent / "resources/sources/arvindguptatoys"
    ap.add_argument("--manifest-dir", type=Path, default=here)
    ap.add_argument("--archive", type=Path, required=True, help="local download root (outside the repo)")
    ap.add_argument("--batch-size", type=int, default=100)
    ap.add_argument("--batches", type=int, default=1, help="0 = until nothing is pending")
    ap.add_argument("--delay", type=float, default=10.0, help="minimum seconds between site requests")
    ap.add_argument("--ia-delay", type=float, default=2.0, help="minimum seconds between archive.org requests")
    ap.add_argument("--min-free-gb", type=float, default=5.0, help="stop when the archive disk has less free")
    ap.add_argument("--remote", help="rclone destination, e.g. gdrive:ArvindGupta-archive")
    ap.add_argument("--prune-stored", action="store_true", help="delete local copies once on the remote")
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("--git", choices=("off", "commit", "push"), default="off",
                    help="commit (and push) manifest + log after every batch")
    ap.add_argument("--trailer", default="", help="extra lines appended to commit messages")
    args = ap.parse_args(argv)

    manifest, log = args.manifest_dir / "manifest.tsv", args.manifest_dir / "batches.tsv"
    args.manifest_dir.mkdir(parents=True, exist_ok=True)
    args.archive.mkdir(parents=True, exist_ok=True)
    rows = reconcile(load(manifest), args.archive, args.retry_failed) or {SEED: row(SEED, status="pending")}
    polite = Polite({HOST: args.delay, IA: args.ia_delay})
    n0 = sum(1 for _ in log.open()) - 1 if log.exists() else 0
    n = n0
    while args.batches == 0 or n - n0 < args.batches:
        if not any(r["status"] == "pending" for r in rows.values()):
            print("nothing pending")
            break
        n += 1
        rows, stats = run_batch(n, rows, args, polite)
        save(manifest, rows)
        if not log.exists():
            log.write_text("\t".join(stats) + "\n", encoding="utf-8")
        with log.open("a", encoding="utf-8") as f:
            f.write("\t".join(map(str, stats.values())) + "\n")
        print(stats, flush=True)
        if args.git != "off":
            msg = (f"Archive Arvind Gupta sources batch {n}: {stats['fetched']} fetched, "
                   f"{stats['failed']} failed, {stats['pending_after']} pending\n\n{args.trailer}").strip()
            git_commit([manifest, log], msg, push=args.git == "push")
        if disk_low(args.archive, args.min_free_gb):
            break


if __name__ == "__main__":
    main()
