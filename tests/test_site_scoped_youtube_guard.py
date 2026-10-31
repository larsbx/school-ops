"""Structural regression tests for the Chrome 145+ site-scoped rule set.

Not a browser integration test: Chrome playback/policy enforcement remains gated.
"""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "tools/browser/site_scoped_youtube_guard"
SPEC = importlib.util.spec_from_file_location("site_guard", ROOT / "build_rules.py")
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def config(**overrides):
    cfg = {
        "allowed_embed_sites": ["school.example.org"],
        "allowed_sites": [],
        "blocked_sites": [],
        "mode": "blacklist",
    }
    cfg.update(overrides)
    return cfg


class YouTubeGuardTests(unittest.TestCase):
    def test_committed_rules_are_reproducible(self):
        example = json.loads((ROOT / "config.json").read_text())
        self.assertEqual(guard.build(example), json.loads((ROOT / "rules.json").read_text()))
        manifest = json.loads((ROOT / "manifest.json").read_text())
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(manifest["minimum_chrome_version"], "145")
        self.assertEqual(manifest["permissions"], ["declarativeNetRequest"])
        self.assertEqual(manifest["declarative_net_request"]["rule_resources"][0]["path"], "rules.json")

    def test_main_frame_youtube_always_highest_priority_block(self):
        for mode in ("blacklist", "whitelist"):
            rules = guard.build(config(mode=mode, allowed_sites=["library.example.org"]))
            main = rules[0]
            self.assertEqual(main["action"], {"type": "block"})
            self.assertEqual(main["condition"]["resourceTypes"], ["main_frame"])
            self.assertTrue({"youtube.com", "youtube-nocookie.com", "youtu.be"} <=
                            set(main["condition"]["requestDomains"]))
            self.assertTrue(all(r["priority"] < main["priority"] for r in rules[1:]))

    def test_only_allowed_top_domains_exempt_embed_resources(self):
        rules = guard.build(config(allowed_embed_sites=["video.example.org", "school.example.org"]))
        sub = rules[1]
        self.assertEqual(sub["action"], {"type": "block"})
        self.assertEqual(sub["condition"]["excludedTopDomains"],
                         ["school.example.org", "video.example.org"])
        self.assertEqual(sub["condition"]["excludedResourceTypes"], ["main_frame"])
        self.assertTrue({"googlevideo.com", "ytimg.com", "youtube.com",
                         "youtube-nocookie.com"} <= set(sub["condition"]["requestDomains"]))

    def test_whitelist_has_default_main_frame_deny(self):
        rules = guard.build(config(mode="whitelist", allowed_sites=["library.example.org"]))
        self.assertEqual([r["id"] for r in rules], [1, 2, 4, 5])
        self.assertEqual(rules[2]["action"]["type"], "allow")
        self.assertEqual(rules[2]["condition"]["requestDomains"],
                         ["library.example.org", "school.example.org"])
        self.assertEqual(rules[3]["action"]["type"], "block")
        self.assertEqual(rules[3]["condition"], {"resourceTypes": ["main_frame"]})
        self.assertGreater(rules[2]["priority"], rules[3]["priority"])

    def test_blacklist_does_not_deny_all_other_sites(self):
        rules = guard.build(config(blocked_sites=["social.example.net"]))
        self.assertEqual([r["id"] for r in rules], [1, 2, 3])
        self.assertEqual(rules[2]["condition"]["requestDomains"], ["social.example.net"])
        self.assertEqual(rules[2]["condition"]["resourceTypes"], ["main_frame"])

    def test_fail_closed_validation(self):
        for cfg in (
            config(allowed_embed_sites=[]),
            config(mode="unrecognized"),
            config(allowed_embed_sites=["www.youtube.com"]),
            config(allowed_sites=["m.youtube.com"]),
            config(blocked_sites=["example.org"]),
            config(blocked_sites=["media.school.example.org"]),
            config(allowed_sites=["library.example.org"], blocked_sites=["example.org"]),
            config(allowed_embed_sites=["https://school.example.org"]),
            config(allowed_embed_sites=["*.example.org"]),
            config(allowed_embed_sites=["127.0.0.1"]),
        ):
            with self.subTest(cfg=cfg), self.assertRaises(ValueError):
                guard.build(cfg)

    def test_normalization_deterministic(self):
        cfg = config(allowed_embed_sites=["video.example.org", "school.example.org",
                                          "video.example.org"])
        self.assertEqual(guard.build(cfg), guard.build(cfg))
        self.assertEqual(guard.build(cfg)[1]["condition"]["excludedTopDomains"],
                         ["school.example.org", "video.example.org"])


if __name__ == "__main__":
    unittest.main()
