"""Inspect an offline Factorio practice receipt against the draft SchoolOps catalog."""
import argparse
import json
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / "curriculum/pilots/factorio/activity.json"
MAX_RECEIPT_BYTES = 1024


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def inspect_receipt(path):
    activity = json.loads(CATALOG.read_text(encoding="utf-8"))
    with path.open("rb") as source:
        data = source.read(MAX_RECEIPT_BYTES + 1)
    if len(data) > MAX_RECEIPT_BYTES:
        raise ValueError("receipt is too large")
    receipt = json.loads(data.decode("utf-8"), object_pairs_hook=unique_fields)
    if receipt != activity["expected_receipt"]:
        raise ValueError("receipt does not match the supported activity, schema, version and completion claim")
    return {
        "schoolops_record": "curriculum/pilots/factorio/README.md",
        "resource_id": activity["resource_id"],
        "activity_id": receipt["activity_id"],
        "material_status": activity["status"],
        "evidence": "unverified_practice_completion_claim"
    }


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
