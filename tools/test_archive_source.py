import contextlib
import hashlib
import io
import tempfile
from types import SimpleNamespace
from unittest import mock
import unittest
from pathlib import Path

import archive_source as a

BASE = "https://www.arvindguptatoys.com/"


class Canonical(unittest.TestCase):
    def test_resolves_relative_and_normalizes_host(self):
        self.assertEqual(a.canonical("arvindgupta/x.pdf", BASE),
                         "https://www.arvindguptatoys.com/arvindgupta/x.pdf")
        self.assertEqual(a.canonical("http://arvindguptatoys.com/a.htm", BASE),
                         "https://www.arvindguptatoys.com/a.htm")

    def test_quotes_once_and_drops_fragment(self):
        self.assertEqual(a.canonical("arvindgupta/Chief%20Seattle.htm#top", BASE),
                         a.canonical("arvindgupta/Chief Seattle.htm", BASE))
        self.assertTrue(a.canonical("arvindgupta/a b.pdf", BASE).endswith("/a%20b.pdf"))

    def test_rejects_non_http(self):
        for href in ("mailto:x@y.z", "javascript:void(0)", "", "#top"):
            self.assertIsNone(a.canonical(href, BASE), href)

    def test_external_kept_but_not_internal(self):
        url = a.canonical("https://archive.org/details/X", BASE)
        self.assertEqual(url, "https://archive.org/details/X")
        self.assertFalse(a.is_internal(url))
        self.assertTrue(a.is_internal(BASE + "x.pdf"))


class LocalPath(unittest.TestCase):
    def test_maps_url_to_host_tree(self):
        root = Path("/r")
        for url in (BASE, BASE + "a/b%20c.pdf"):
            self.assertEqual(a.local_path(root, url), root / a.HOST / "_urls" /
                             hashlib.sha256(url.encode()).hexdigest()[:2] /
                             hashlib.sha256(url.encode()).hexdigest())

    def test_stays_inside_root(self):
        p = a.local_path(Path("/r"), BASE + "a/%2e%2e/%2e%2e/etc/passwd")
        self.assertTrue(str(p).startswith("/r/www.arvindguptatoys.com/"))


class Links(unittest.TestCase):
    def test_extracts_href_src_with_titles(self):
        html = '<a href="b.pdf"> Book\n B </a><img src="i.png"><a href="mailto:q">m</a>'
        self.assertEqual(a.extract_links(html, BASE),
                         [(BASE + "b.pdf", "Book B"), (BASE + "i.png", "")])


class Manifest(unittest.TestCase):
    def test_discover_adds_new_only_and_classifies(self):
        rows = {BASE: a.row(BASE, status="fetched")}
        out = a.discover(rows, [(BASE, "home"), (BASE + "x.pdf", "X"),
                                ("https://youtu.be/q", "vid")], found_on=BASE)
        self.assertEqual(rows.keys(), {BASE})  # input untouched
        self.assertEqual(out[BASE]["status"], "fetched")
        self.assertEqual(out[BASE + "x.pdf"], a.row(BASE + "x.pdf", status="pending",
                                                    title="X", found_on=BASE))
        self.assertEqual(out["https://youtu.be/q"]["status"], "external")

    def test_round_trip_is_sorted_and_lossless(self):
        rows = a.discover({}, [(BASE + "z.pdf", "Z\tq"), (BASE + "a.pdf", "A")], found_on=BASE)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.tsv"
            a.save(p, rows)
            self.assertEqual(rows[BASE + "z.pdf"]["title"], "Z q")
            self.assertEqual(a.load(p), rows)
            urls = [l.split("\t")[0] for l in p.read_text().splitlines()[1:]]
            self.assertEqual(urls, sorted(urls))

    def test_reconcile_requeues_local_only_rows_missing_on_disk(self):
        rows = {BASE + "a": a.row(BASE + "a", status="fetched"),
                BASE + "b": a.row(BASE + "b", status="stored"),
                BASE + "c": a.row(BASE + "c", status="failed:404")}
        with tempfile.TemporaryDirectory() as d:
            out = a.reconcile(rows, Path(d), retry_failed=False)
            self.assertEqual([out[k]["status"] for k in sorted(out)], ["pending", "stored", "failed:404"])
            out = a.reconcile(rows, Path(d), retry_failed=True)
            self.assertEqual(out[BASE + "c"]["status"], "pending")


IA = "https://archive.org/"


class ArchiveOrg(unittest.TestCase):
    def test_item_ids(self):
        self.assertEqual(a.ia_item(IA + "details/Kitten"), "Kitten")
        self.assertEqual(a.ia_item(IA + "details/Kitten/page/n5"), "Kitten")
        self.assertEqual(a.ia_item(IA + "download/Kitten/"), "Kitten")
        self.assertIsNone(a.ia_item(IA + "download/Kitten/k.pdf"))
        self.assertIsNone(a.ia_item(IA + "compress/Kitten"))
        self.assertIsNone(a.ia_item(BASE + "details/Kitten"))

    def test_fetchable_covers_site_ia_items_and_ia_files(self):
        self.assertTrue(a.fetchable(BASE + "x.pdf"))
        self.assertTrue(a.fetchable(IA + "details/Kitten"))
        self.assertTrue(a.fetchable(IA + "download/Kitten/k.pdf"))
        self.assertFalse(a.fetchable(IA + "compress/Kitten"))
        self.assertFalse(a.fetchable("https://www.youtube.com/watch?v=q"))

    def test_reconcile_promotes_newly_fetchable_externals(self):
        rows = {u: a.row(u, status="external") for u in (IA + "details/K", "https://youtu.be/q")}
        out = a.reconcile(rows, Path("/nonexistent"), retry_failed=False)
        self.assertEqual(out[IA + "details/K"]["status"], "pending")
        self.assertEqual(out["https://youtu.be/q"]["status"], "external")

    def test_ia_files_keeps_originals_except_bookkeeping(self):
        meta = {"metadata": {"title": "Kitten"}, "files": [
            {"name": "k.pdf", "source": "original", "format": "Image Container PDF", "size": "31"},
            {"name": "k_djvu.txt", "source": "derivative", "format": "DjVuTXT"},
            {"name": "K_meta.xml", "source": "original", "format": "Metadata"},
            {"name": "__ia_thumb.jpg", "source": "original", "format": "Item Tile"},
            {"name": "a b/c.zip", "source": "original", "format": "ZIP"}]}
        self.assertEqual(a.ia_files("K", meta), [(IA + "download/K/k.pdf", "Kitten"),
                                                 (IA + "download/K/a%20b/c.zip", "Kitten")])

    def test_order_puts_site_before_archive_org(self):
        urls = [IA + "details/A", BASE + "z.pdf", BASE + "a.pdf"]
        self.assertEqual(sorted(urls, key=a.order), [BASE + "a.pdf", BASE + "z.pdf", IA + "details/A"])


class Recovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.args = SimpleNamespace(archive=self.root, remote='fake:archive',
                                    prune_stored=False, batch_size=1, min_free_gb=0)

    def local(self, url, content=b'original'):
        dest = a.local_path(self.root, url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        return a.row(url, status='fetched', bytes=len(content),
                     sha256=hashlib.sha256(content).hexdigest())

    def test_url_aliases_have_distinct_paths_and_bytes(self):
        urls = [BASE + x for x in ('guide/', 'guide/index.html', 'guide',
                                   'guide/child.pdf', 'a?x=1/2', 'a?x=1%2F2',
                                   'a%2Fb', 'a/b')]
        self.assertEqual(len(urls), len({a.local_path(self.root, u) for u in urls}))
        for i, u in enumerate(urls):
            self.local(u, str(i).encode())
        for i, u in enumerate(urls):
            self.assertEqual(str(i).encode(), a.local_path(self.root, u).read_bytes())

    def test_legacy_alias_migrates_only_matching_hash(self):
        u, v = BASE + 'guide/', BASE + 'guide/index.html'
        old = a.legacy_local_path(self.root, u)
        self.assertEqual(old, a.legacy_local_path(self.root, v))
        old.parent.mkdir(parents=True); old.write_bytes(b'second')
        rows = {u: a.row(u, status='fetched', sha256=hashlib.sha256(b'first').hexdigest()),
                v: a.row(v, status='fetched', sha256=hashlib.sha256(b'second').hexdigest())}
        out = a.reconcile(rows, self.root, False)
        self.assertEqual('pending', out[u]['status'])
        self.assertEqual('fetched', out[v]['status'])
        self.assertEqual(b'second', a.local_path(self.root, v).read_bytes())

    def test_upload_only_batches_are_bounded_and_retry_without_pruning_on_failure(self):
        u, v = BASE + 'a.pdf', BASE + 'b.pdf'
        rows = {u: self.local(u), v: self.local(v)}
        polite = mock.Mock()
        self.args.prune_stored = True
        with mock.patch.object(a, 'rclone_store', return_value=set()) as upload:
            rows, stats = a.run_batch(1, rows, self.args, polite)
            upload.assert_called_once_with(self.root, self.args.remote, [u])
        self.assertEqual('fetched', rows[u]['status'])
        self.assertTrue(a.local_path(self.root, u).exists())
        with mock.patch.object(a, 'rclone_store', side_effect=[{u}, {v}]):
            rows, first = a.run_batch(2, rows, self.args, polite)
            rows, second = a.run_batch(3, rows, self.args, polite)
        self.assertEqual([1, 1], [first['stored'], second['stored']])
        self.assertTrue(all(r['status'] == 'stored' for r in rows.values()))
        self.assertFalse(a.local_path(self.root, u).exists())
        polite.allowed.assert_not_called()

    def test_main_resumes_upload_when_no_pending_urls_and_stops_on_failure(self):
        u = BASE + 'a.pdf'
        manifest_dir = self.root / 'meta'; manifest_dir.mkdir()
        a.save(manifest_dir / 'manifest.tsv', {u: self.local(u)})
        argv = ['--archive', str(self.root), '--manifest-dir', str(manifest_dir),
                '--remote', 'fake:archive', '--batches', '0', '--min-free-gb', '0']
        with mock.patch.object(a, 'Polite'), contextlib.redirect_stdout(io.StringIO()):
            with mock.patch.object(a, 'rclone_store', return_value=set()) as upload:
                a.main(argv)
                self.assertEqual(1, upload.call_count)
            self.assertEqual('fetched', a.load(manifest_dir / 'manifest.tsv')[u]['status'])
            with mock.patch.object(a, 'rclone_store', return_value={u}) as upload:
                a.main(argv)
                self.assertEqual(1, upload.call_count)
        self.assertEqual('stored', a.load(manifest_dir / 'manifest.tsv')[u]['status'])

    def test_robots_checks_actual_metadata_endpoint_before_request(self):
        u = IA + 'details/Kitten'
        rows = {u: a.row(u, status='pending')}
        polite = mock.Mock(); polite.allowed.return_value = False
        with mock.patch.object(a, 'expand') as expand:
            out, stats = a.run_batch(1, rows, self.args, polite)
        polite.allowed.assert_called_once_with(IA + 'metadata/Kitten')
        polite.wait.assert_not_called(); expand.assert_not_called()
        self.assertEqual('failed:robots', out[u]['status'])
        polite.allowed.return_value = True
        with mock.patch.object(a, 'expand', return_value=({'status': 'indexed'}, [])):
            a.run_batch(2, rows, self.args, polite)
        polite.wait.assert_called_once_with(IA + 'metadata/Kitten')

    def test_invalid_batch_sizes_rejected_before_side_effects(self):
        for size in ('0', '-1'):
            with mock.patch.object(a, 'load') as load, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as err:
                    a.main(['--archive', str(self.root / 'unused'), '--batch-size', size,
                            '--batches', '0', '--git', 'push'])
                self.assertEqual(2, err.exception.code)
                load.assert_not_called()
                self.assertFalse((self.root / 'unused').exists())

    def test_missing_rclone_retains_local_copy(self):
        u = BASE + 'a.pdf'; self.local(u)
        with mock.patch.object(a.subprocess, 'run', side_effect=FileNotFoundError), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(set(), a.rclone_store(self.root, 'fake:archive', [u]))
        self.assertTrue(a.local_path(self.root, u).exists())


if __name__ == "__main__":
    unittest.main()
