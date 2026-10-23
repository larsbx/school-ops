#!/usr/bin/env python3
"""Batched, resumable, polite archive of a website, tracked by a TSV manifest.

The manifest (committed to the repo) holds metadata only: one row per discovered
URL with its status. Downloaded files live outside the repo in --archive and are
optionally copied to an rclone remote. Any session can continue from the manifest.

Status: pending | fetched (local copy only) | stored (on remote) | failed:<why> | external
"""
import argparse
import hashlib
import re
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
ALIASES = {"arvindguptatoys.com", HOST}
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
    scheme, host = ("https", HOST) if host in ALIASES else (parts.scheme, host)
    path = quote(unquote(parts.path) or "/", safe="/:@!$&'()*+,;=~-._")
    return urlunsplit((scheme, host, path, parts.query, ""))


def is_internal(url):
    return urlsplit(url).netloc == HOST


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
            new[url] = row(url, status="pending" if is_internal(url) else "external",
                           title=clean(title), found_on=found_on)
    return {**rows, **new}


def reconcile(rows, root, retry_failed):
    """Requeue rows whose only copy is gone (new container) and, optionally, failures."""
    def requeue(r):
        lost = r["status"] == "fetched" and not local_path(root, r["url"]).is_file()
        failed = retry_failed and r["status"].startswith("failed")
        return {**r, "status": "pending"} if lost or failed else r
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


def robots(delay):
    rp = urllib.robotparser.RobotFileParser(urljoin(SEED, "/robots.txt"))
    rp.read()
    return rp, max(delay, float(rp.crawl_delay(UA) or 0))


def run_batch(n, rows, args, rp, delay):
    todo = [u for u in sorted(rows) if rows[u]["status"] == "pending"][: args.batch_size]
    started, fetched = now(), []
    for i, url in enumerate(todo):
        if not rp.can_fetch(UA, url):
            rows = {**rows, url: {**rows[url], "status": "failed:robots"}}
            continue
        if i:
            time.sleep(delay)
        fields, html = fetch(url, local_path(args.archive, url))
        rows = {**rows, url: {**rows[url], **fields}}
        if html is not None:
            rows = discover(rows, extract_links(html, url), found_on=url)
        if fields["status"] == "fetched":
            fetched.append(url)
        print(f"[{n}:{i + 1}/{len(todo)}] {fields['status']:<14} {url}", flush=True)
    stored = rclone_store(args.archive, args.remote, fetched) if args.remote and fetched else set()
    rows = {u: ({**r, "status": "stored"} if u in stored else r) for u, r in rows.items()}
    if args.prune_stored:
        for u in stored:
            local_path(args.archive, u).unlink(missing_ok=True)
    stats = {"batch": n, "started": started, "ended": now(), "attempted": len(todo),
             "fetched": len(fetched), "stored": len(stored),
             "failed": sum(rows[u]["status"].startswith("failed") for u in todo),
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
    ap.add_argument("--delay", type=float, default=10.0, help="minimum seconds between requests")
    ap.add_argument("--remote", help="rclone destination, e.g. gdrive:ArvindGupta-archive")
    ap.add_argument("--prune-stored", action="store_true", help="delete local copies once on the remote")
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("--git", choices=("off", "commit", "push"), default="off",
                    help="commit (and push) manifest + log after every batch")
    ap.add_argument("--trailer", default="", help="extra lines appended to commit messages")
    args = ap.parse_args(argv)

    manifest, log = args.manifest_dir / "manifest.tsv", args.manifest_dir / "batches.tsv"
    args.manifest_dir.mkdir(parents=True, exist_ok=True)
    rows = reconcile(load(manifest), args.archive, args.retry_failed) or {SEED: row(SEED, status="pending")}
    rp, delay = robots(args.delay)
    n0 = sum(1 for _ in log.open()) - 1 if log.exists() else 0
    n = n0
    while args.batches == 0 or n - n0 < args.batches:
        if not any(r["status"] == "pending" for r in rows.values()):
            print("nothing pending")
            break
        n += 1
        rows, stats = run_batch(n, rows, args, rp, delay)
        save(manifest, rows)
        if not log.exists():
            log.write_text("\t".join(stats) + "\n", encoding="utf-8")
        with log.open("a", encoding="utf-8") as f:
            f.write("\t".join(map(str, stats.values())) + "\n")
        print(stats, flush=True)
        if args.git != "off":
            msg = (f"Archive arvindguptatoys.com batch {n}: {stats['fetched']} fetched, "
                   f"{stats['failed']} failed, {stats['pending_after']} pending\n\n{args.trailer}").strip()
            git_commit([manifest, log], msg, push=args.git == "push")


if __name__ == "__main__":
    main()
