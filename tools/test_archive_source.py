import tempfile
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
        self.assertEqual(a.local_path(root, BASE), root / "www.arvindguptatoys.com/index.html")
        self.assertEqual(a.local_path(root, BASE + "a/b%20c.pdf"),
                         root / "www.arvindguptatoys.com/a/b c.pdf")

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


if __name__ == "__main__":
    unittest.main()
