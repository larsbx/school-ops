"""Inspect an offline Factorio practice receipt against the draft SchoolOps catalog."""
import argparse
import json
from pathlib import Path

PILOT_ROOT = Path("curriculum/pilots/factorio")
REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_RECEIPT_BYTES = 1024
MAX_CATALOG_BYTES = 4096


def _claim(activity_id, version):
    return {
        "schema": "schoolops.factorio.practice.v1",
        "activity_id": activity_id,
        "mod_version": version,
        "result": "completed",
    }


# Known, original draft catalog schemas only. Metadata never approves content,
# authorizes a provider export, or elevates an unsigned practice receipt.
KNOWN_CATALOGS = {
    PILOT_ROOT: {
        "status": "draft",
        "resource_id": "R-FACTORIO-001",
        "expected_receipt": _claim("L-FACTORIO-SMELTING-01", "0.2.0"),
        "additional_expected_receipts": [_claim("L-FACTORIO-SMELTING-01", "0.3.0")],
    },
    PILOT_ROOT / "ratio-loading-bay": {
        "status": "draft",
        "resource_id": "R-FACTORIO-002",
        "expected_receipt": _claim("L-FACTORIO-RATIO-01", "0.3.0"),
    },
    PILOT_ROOT / "factory-supply-order": {
        "status": "draft",
        "resource_id": "R-FACTORIO-003",
        "expected_receipt": _claim("L-FACTORIO-SUPPLY-01", "0.3.0"),
    },
}
REGISTERED_ACTIVITIES = tuple(KNOWN_CATALOGS)


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _load_known_catalog(directory):
    catalog = REPO_ROOT / directory / "activity.json"
    with catalog.open("rb") as source:
        data = source.read(MAX_CATALOG_BYTES + 1)
    if len(data) > MAX_CATALOG_BYTES:
        raise ValueError("activity catalog exceeds size limit")

    def reject_nonfinite(_):
        raise ValueError("non-finite activity catalog value")

    activity = json.loads(data.decode("utf-8"), object_pairs_hook=unique_fields,
                          parse_constant=reject_nonfinite)
    # Exact equality also rejects unknown fields, content-rights assertions,
    # version additions, activity swaps and non-draft teaching status.
    if type(activity) is not dict or activity != KNOWN_CATALOGS[directory]:
        raise ValueError("activity catalog differs from supported draft metadata")
    return activity


def inspect_receipt(path):
    with path.open("rb") as source:
        data = source.read(MAX_RECEIPT_BYTES + 1)
    if len(data) > MAX_RECEIPT_BYTES:
        raise ValueError("receipt is too large")
    receipt = json.loads(data.decode("utf-8"), object_pairs_hook=unique_fields)
    # Validate all known catalog entries before classifying any receipt; an
    # unrelated malformed or promoted manifest must not pass unnoticed.
    catalogs = {directory: _load_known_catalog(directory) for directory in REGISTERED_ACTIVITIES}
    for directory, activity in catalogs.items():
        supported = [activity["expected_receipt"], *activity.get("additional_expected_receipts", [])]
        if any(receipt == expected for expected in supported):
            return {
                "schoolops_record": (directory / "README.md").as_posix(),
                "resource_id": activity["resource_id"],
                "activity_id": receipt["activity_id"],
                "material_status": activity["status"],
                "evidence": "unverified_practice_completion_claim"
            }
    raise ValueError("receipt does not match the supported activity, schema, version and completion claim")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    try:
        result = inspect_receipt(args.receipt)
    except (ValueError, OSError, RecursionError) as error:
        parser.exit(2, f"Invalid or unreadable practice receipt ({type(error).__name__}).\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
