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
  only `stored` rows are durable.
- **Verify:** `sha256` lets you check any copy against the manifest.
