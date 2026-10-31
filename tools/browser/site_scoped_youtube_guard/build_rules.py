#!/usr/bin/env python3
"""Build the MV3 static DNR rules from administrator-owned configuration.

No learner data, passwords, or browser-side settings UI are stored here.
"""
import json
from ipaddress import ip_address
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config.json"
OUTPUT = ROOT / "rules.json"

YOUTUBE_PAGE_DOMAINS = ["youtube.com", "youtube-nocookie.com", "youtu.be"]
YOUTUBE_RESOURCE_DOMAINS = [
    "youtube.com",
    "youtube-nocookie.com",
    "youtu.be",
    "youtubei.googleapis.com",
    "youtube.googleapis.com",
    "googlevideo.com",
    "ytimg.com",
]


def hostname(value):
    if not isinstance(value, str):
        raise ValueError("Domain values must be strings")
    domain = value.strip().lower().rstrip(".")
    if not domain or any(c in domain for c in "/:*?@# "):
        raise ValueError(f"Provide a hostname, not a URL or wildcard: {value!r}")
    if domain == "localhost":
        return domain
    try:
        ip_address(domain)
    except ValueError:
        pass
    else:
        raise ValueError("IP addresses are not supported by this domain policy")
    if "." not in domain:
        raise ValueError(f"Use a fully qualified domain: {value!r}")
    if any(
        not part or len(part) > 63
        or part.startswith("-") or part.endswith("-")
        or not all(c.isascii() and (c.isalnum() or c == "-") for c in part)
        for part in domain.split(".")
    ):
        raise ValueError(f"Invalid hostname: {value!r}")
    return domain


def domains(values):
    if not isinstance(values, list):
        raise ValueError("Domain settings must be lists")
    return sorted(set(hostname(item) for item in values))


def overlaps(left, right):
    """Chrome DNR domain matching includes subdomains."""
    return left == right or left.endswith("." + right) or right.endswith("." + left)


def build(cfg):
    allowed_embed = domains(cfg.get("allowed_embed_sites", []))
    if not allowed_embed:
        raise ValueError("At least one approved embedding website is required")
    mode = cfg.get("mode", "blacklist")
    if mode not in ("blacklist", "whitelist"):
        raise ValueError("mode must be blacklist or whitelist")
    allowed = domains(cfg.get("allowed_sites", []))
    blocked = domains(cfg.get("blocked_sites", []))
    approved = sorted(set(allowed + allowed_embed))
    if any(overlaps(a, yt) for a in approved for yt in YOUTUBE_PAGE_DOMAINS):
        raise ValueError("Do not approve YouTube page domains or their subdomains")
    if any(overlaps(a, b) for a in approved for b in blocked):
        raise ValueError("Approved and blocked domains must not overlap")

    # Top-level YouTube navigation is always denied, even from an approved tab.
    rules = [
        {
            "id": 1,
            "priority": 100,
            "action": {"type": "block"},
            "condition": {
                "requestDomains": YOUTUBE_PAGE_DOMAINS,
                "resourceTypes": ["main_frame"],
            },
        },
        {
            "id": 2,
            "priority": 90,
            "action": {"type": "block"},
            "condition": {
                "requestDomains": YOUTUBE_RESOURCE_DOMAINS,
                "excludedTopDomains": allowed_embed,
                "excludedResourceTypes": ["main_frame"],
            },
        },
    ]
    if blocked:
        rules.append({
            "id": 3,
            "priority": 80,
            "action": {"type": "block"},
            "condition": {
                "requestDomains": blocked, "resourceTypes": ["main_frame"]
            },
        })
    if mode == "whitelist":
        rules.extend([
            {
                "id": 4,
                "priority": 50,
                "action": {"type": "allow"},
                "condition": {
                    "requestDomains": approved, "resourceTypes": ["main_frame"]
                },
            },
            {
                "id": 5,
                "priority": 10,
                "action": {"type": "block"},
                "condition": {"resourceTypes": ["main_frame"]},
            },
        ])
    return rules


if __name__ == "__main__":
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    OUTPUT.write_text(json.dumps(build(cfg), indent=2) + "\n", encoding="utf-8")
    print(f"Generated {OUTPUT} for {cfg['allowed_embed_sites']}")
    if "approved-site.invalid" in cfg["allowed_embed_sites"]:
        print("WARNING: Configure the actual school site before deployment.")
