# Arvind Gupta source archive (arvindguptatoys.com)

Metadata for a private analysis archive of [arvindguptatoys.com](https://www.arvindguptatoys.com/),
Arvind Gupta's collection of toy-making guides, science books, and translations,
including the [archive.org](https://archive.org/) items and files it links to. Many
of the books are hosted there.
This is source material under study, not a reviewed resource. Nothing here is in
the [resource register](../../README.md).

**The repository holds metadata only.** Downloaded files live outside the repo:
locally, and optionally on a private rclone remote. Much of the site is books by
other authors whose reuse rights are **unresolved**. Do not commit, share, or
redistribute the copies. Cite works by their source URL.

## Files

| File | Contents |
| --- | --- |
| [manifest.tsv](manifest.tsv) | One row per discovered URL, sorted by URL |
| [batches.tsv](batches.tsv) | Append-only log, one row per batch |
| [../../../tools/archive_source.py](../../../tools/archive_source.py) | The crawler; its tests are in `tools/test_archive_source.py` |

Manifest columns: `url`, `status`, `content_type`, `bytes`, `sha256`, `fetched_at`,
`title` (link text where first found), `found_on` (first referring page).

| Status | Meaning |
| --- | --- |
| `pending` | Discovered on the site or as a linked archive.org item or file; not yet fetched |
| `fetched` | Downloaded and hashed, but the only copy is local (lost with its container) |
| `stored` | Downloaded and copied to the rclone remote |
| `indexed` | archive.org item expanded through its metadata API into rows for its original files (`bytes` is their total) |
| `failed:<why>` | HTTP code or error class; retry with `--retry-failed` |
| `external` | Other off-site link (YouTube, other publishers); recorded, not fetched |

## Continue the archive

```sh
python3 -I tools/archive_source.py --archive ~/arvind-archive --batches 0 --git push \
  [--remote gdrive:ArvindGupta-archive --prune-stored]
```

- **Politeness:** per host, waits at least 10 s between site requests and 2 s between
  archive.org requests, or longer if `robots.txt` asks. It skips any path that
  `robots.txt` disallows.
- **Order:** site URLs first, then archive.org items and files. For an archive.org
  item it downloads the uploaded originals only, skipping generated derivatives
  (OCR text, page images) and bookkeeping files.
- **Disk:** stops cleanly once free space drops under `--min-free-gb` (default 5).
- **Resume:** each batch (default 100 URLs) rewrites the manifest atomically and
  appends to the log. `--git push` commits and pushes both after every batch.
  On a fresh machine, `fetched` rows with no local file go back to `pending`, so
  upload retries include existing local `fetched` rows even if no URLs remain
  pending. Each upload batch is bounded by `--batch-size`; a failed upload-only
  batch stops without pruning, ready for a later retry. `stored` records remote
  copy success, not independent long-term durability or a rights review.
- **Verify:** `sha256` lets you check any copy against the manifest.

## Archive paths and offline validation

New copies use `<host>/_urls/<digest-prefix>/<sha256-of-url>` below the archive
root. Exact URL identities remain distinct for directory/index, file/directory,
encoded path and query variants. The manifest maps each URL to its content hash;
the path digest identifies the URL, not its contents.

On resume, a legacy local `fetched` copy is moved into the new layout only when
its content hash matches the row. Missing or mismatched legacy copies return to
`pending`. Existing `stored` rows are not rewritten or independently verified;
legacy remote archives need a separate hash audit before relying on old aliases.
`--batch-size` must be positive, `--batches` nonnegative, and pruning requires a
remote. Robots checks and pacing use the actual Archive.org metadata endpoint.

Run `python -m unittest discover -s tools -p 'test_archive_source.py' -v`.
Tests mock network and rclone effects; they do not crawl, upload, commit or push.
