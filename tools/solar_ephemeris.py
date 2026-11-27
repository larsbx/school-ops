#!/usr/bin/env python3
"""Reproduce the review-only solar packet from pinned NASA/JPL responses.

Offline verification is the default. Acquisition is an explicit, sequential
operation into a new directory; it never updates the accepted snapshot.
Only the standard library is needed on Python 3.11 through 3.13.
"""
from __future__ import annotations

import argparse
import copy
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "curriculum/astronomy/grade-4-daylight-pilot/solar-companion"
UTC = timezone.utc
THRESHOLD = Fraction(-5, 6)
MONTHS = {m: i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


class SourceError(ValueError):
    """Unusable or inconsistent input; never substitute synthetic source data."""


def dumps(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def decimal(value, *, allow_missing=False):
    if allow_missing and (value is None or str(value).strip() in ("", "n.a.")):
        return None
    if isinstance(value, bool):
        raise SourceError("Boolean is not a numerical source value")
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise SourceError("Invalid numerical source value") from exc
    if not number.is_finite():
        raise SourceError("Nonfinite source value")
    return number


def bearing_tick(value):
    """Nearest 15-degree tick; clockwise half ties; canonical north is zero."""
    if value is None:
        return None
    angle = decimal(value)
    if not 0 <= angle <= 360:
        raise SourceError("Bearing outside 0..360 degrees")
    return (int((angle / 15).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) % 24) * 15


def circular_difference(start, end, direction="clockwise"):
    if start is None or end is None:
        return None
    a, b = decimal(start), decimal(end)
    if not 0 <= a <= 360 or not 0 <= b <= 360:
        raise SourceError("Invalid circular direction")
    if direction == "clockwise":
        return (b - a + 360) % 360
    if direction == "counterclockwise":
        return (a - b + 360) % 360
    raise SourceError("Direction must be stated explicitly")


def parse_time(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise SourceError("Expected a valid 24-hour HH:MM clock reading")
    h, m = map(int, value.split(":"))
    return h * 60 + m


def daylight_minutes(rise, setting):
    """Same-date interval only. Missing is unknown; no midnight-wrap invention."""
    if rise is None or setting is None:
        return None
    a, b = parse_time(rise), parse_time(setting)
    if b <= a:
        raise SourceError("This packet requires a positive same-date interval")
    return b - a


def fixed_zone(minutes):
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not -720 <= minutes <= 840:
        raise SourceError("Invalid fixed UTC offset in minutes")
    return timezone(timedelta(minutes=minutes))


def local_midnight(day, offset):
    return datetime.combine(date.fromisoformat(day), datetime.min.time(), fixed_zone(offset))


def parse_epoch(text):
    match = re.fullmatch(r"(\d{4})-([A-Za-z]{3})-(\d\d) (\d\d):(\d\d):(\d\d)(?:\.(\d{1,6}))?", text.strip())
    if not match or match[2] not in MONTHS:
        raise SourceError("Unexpected Horizons calendar timestamp")
    try:
        return datetime(int(match[1]), MONTHS[match[2]], int(match[3]),
                        int(match[4]), int(match[5]), int(match[6]),
                        int((match[7] or "0").ljust(6, "0")), tzinfo=UTC)
    except ValueError as exc:
        raise SourceError("Invalid Horizons calendar timestamp") from exc


def parse_horizons(raw):
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise SourceError("Response is not JSON") from exc
    if not isinstance(obj, dict) or obj.get("error"):
        raise SourceError("Provider error response")
    if obj.get("signature") != {"source": "NASA/JPL Horizons API", "version": "1.2"}:
        raise SourceError("Unreviewed provider/API signature")
    result = obj.get("result", "")
    if not isinstance(result, str) or result.count("$$SOE") != 1 or result.count("$$EOE") != 1:
        raise SourceError("Missing or duplicate ephemeris delimiters")
    header, rest = result.split("$$SOE")
    body, _ = rest.split("$$EOE")
    expected = (
        r"Target body name:\s*Sun \(10\)\s*\{source: DE441\}",
        r"Center body name:\s*Earth \(399\)\s*\{source: DE441\}",
        r"Center pole/equ\s*:\s*ITRF93",
        r"Atmos refraction:\s*NO \(AIRLESS\)",
        r"Calendar mode\s*:\s*Gregorian",
        r"Date__\(UT\)__HR:MN:(?:SS|SC\.fff), , ,Azi_\(a-app\), Elev_\(a-app\),",
    )
    if not all(re.search(pattern, header) for pattern in expected):
        raise SourceError("Wrong target, frame, clock, calendar, columns or refraction")
    rows = []
    for fields in csv.reader(io.StringIO(body.strip())):
        if len(fields) != 6 or fields[-1].strip():
            raise SourceError("Unexpected ephemeris column shape")
        stamp = parse_epoch(fields[0])
        az = decimal(fields[3], allow_missing=True)
        el = decimal(fields[4], allow_missing=True)
        if az is not None and not 0 <= az <= 360:
            raise SourceError("Out-of-range source azimuth")
        if el is not None and not -90 <= el <= 90:
            raise SourceError("Out-of-range source elevation")
        if rows and stamp <= rows[-1]["utc"]:
            raise SourceError("Duplicate or out-of-order source epochs")
        rows.append({"utc": stamp, "azimuth": az, "elevation": el})
    if not rows:
        raise SourceError("Empty ephemeris table")
    return header, rows, result


def pinned_file(data_dir, relative, expected_hash):
    path = (data_dir / relative).resolve()
    if not path.is_relative_to(data_dir.resolve()):
        raise SourceError("Source path leaves data directory")
    data = path.read_bytes()
    if digest(data) != expected_hash:
        raise SourceError("Source checksum mismatch: " + relative)
    return data


def read_source(data_dir, manifest, entry):
    raw = pinned_file(data_dir, entry["raw_path"], entry["raw_sha256"])
    request_raw = pinned_file(data_dir, entry["request_path"], entry["request_sha256"])
    saved_text = pinned_file(data_dir, entry["text_path"], entry["text_sha256"])
    meta = json.loads(request_raw)
    header, rows, result = parse_horizons(raw)
    if saved_text.decode("utf-8") != result:
        raise SourceError("Decoded text does not match raw response")
    if meta["sha256"] != entry["raw_sha256"] or meta["http_status"] != 200:
        raise SourceError("Request receipt disagrees with raw response")
    if meta.get("api_signature") != {"source": "NASA/JPL Horizons API", "version": manifest["api_version"]}:
        raise SourceError("Request receipt API signature disagrees")
    if meta["site_id"] != entry["site_id"] or meta["packet_local_date"] != entry["local_date"]:
        raise SourceError("Wrong site or day in source receipt")
    site = manifest["sites"][entry["site_id"]]
    if decimal(meta["packet_fixed_utc_offset_hours"]) * 60 != site["fixed_utc_offset_minutes"]:
        raise SourceError("Wrong clock in receipt")
    params = meta["parameters"]
    required = {"format": "json", "COMMAND": "'10'", "EPHEM_TYPE": "'OBSERVER'",
                "CENTER": "'coord@399'", "COORD_TYPE": "'GEODETIC'", "QUANTITIES": "'4'",
                "CSV_FORMAT": "'YES'", "APPARENT": "'AIRLESS'", "CAL_TYPE": "'GREGORIAN'",
                "ELEV_CUT": "'-90'", "SKIP_DAYLT": "'NO'", "TIME_DIGITS": "'SECONDS'"}
    if any(params.get(k) != v for k, v in required.items()):
        raise SourceError("Unreviewed source request conventions")
    role_keys = {"minute": {"START_TIME", "STOP_TIME", "STEP_SIZE"},
                 "midpoints": {"TLIST", "TLIST_TYPE", "TIME_TYPE"}}
    if entry["kind"] not in role_keys or set(params) != set(required) | {"SITE_COORD"} | role_keys[entry["kind"]]:
        raise SourceError("Unexpected request parameters or source role")
    url = urlsplit(meta["request_url"])
    if (url.scheme, url.netloc, url.path) != ("https", "ssd.jpl.nasa.gov", "/api/horizons.api"):
        raise SourceError("Wrong provider endpoint")
    if parse_qs(url.query) != {key: [value] for key, value in params.items()}:
        raise SourceError("URL and saved request parameters disagree")
    expected_coords = [decimal(site[k]) for k in ("longitude_deg_east", "latitude_deg", "ellipsoid_height_km")]
    if [decimal(meta[k]) for k in ("longitude_deg_east", "latitude_deg", "ellipsoid_height_km")] != expected_coords:
        raise SourceError("Receipt coordinate fields disagree with manifest")
    if [decimal(v) for v in params["SITE_COORD"].strip("'").split(",")] != expected_coords:
        raise SourceError("Wrong requested coordinates")
    coordinate_header = re.search(r"Center geodetic\s*:\s*([^\{]+)\{", header)
    if not coordinate_header:
        raise SourceError("Missing returned coordinates")
    returned_coords = [decimal(v) for v in coordinate_header[1].strip().split(",")]
    if len(returned_coords) != 3 or any(abs(a - b) > Decimal("0.000001") for a, b in zip(returned_coords, expected_coords)):
        raise SourceError("Returned coordinates disagree with requested coordinates")
    midnight = local_midnight(entry["local_date"], site["fixed_utc_offset_minutes"]).astimezone(UTC)
    if entry["kind"] == "minute":
        expected_dates = [midnight + timedelta(minutes=i) for i in range(1441)]
        if [r["utc"] for r in rows] != expected_dates:
            raise SourceError("Incomplete, wrong-date or non-minute day series")
        for key, stamp in (("START_TIME", midnight), ("STOP_TIME", midnight + timedelta(days=1))):
            if params.get(key) != "'" + stamp.strftime("%Y-%m-%d %H:%M") + "'":
                raise SourceError("Request date/UTC offset mismatch")
        if params.get("STEP_SIZE") != "'1 m'":
            raise SourceError("Unexpected source sampling interval")
    elif entry["kind"] == "midpoints":
        requested = re.findall(r"'([^']+)'", params.get("TLIST", ""))
        if params.get("TLIST_TYPE") != "'CAL'" or params.get("TIME_TYPE") != "'UT'":
            raise SourceError("Unexpected midpoint clock/calendar")
        expected_dates = [datetime.fromisoformat(v).replace(tzinfo=UTC) for v in requested]
        if len(rows) != 2 or [r["utc"] for r in rows] != expected_dates:
            raise SourceError("Wrong or incomplete midpoint samples")
    else:
        raise SourceError("Unknown source role")
    return header, rows


def crossing_brackets(rows):
    """Any missing/gapped elevation prevents a complete day's event inference."""
    if any(r["elevation"] is None for r in rows):
        return {"status": "source_missing", "events": []}
    if any(b["utc"] - a["utc"] != timedelta(minutes=1) for a, b in zip(rows, rows[1:])):
        return {"status": "source_incomplete", "events": []}
    events = []
    for a, b in zip(rows, rows[1:]):
        low, high = Fraction(a["elevation"]), Fraction(b["elevation"])
        if low < THRESHOLD <= high:
            events.append(("rise", a, b))
        elif low > THRESHOLD >= high:
            events.append(("set", a, b))
    if [e[0] for e in events] != ["rise", "set"]:
        # No event can mean polar day, polar night, truncation or another cause.
        # This selected non-polar packet does not classify which one.
        return {"status": "no_unique_rise_set_pair", "events": []}
    return {"status": "complete", "events": events}


def rounded_event(kind, start, end, midpoint):
    if end["utc"] - start["utc"] != timedelta(minutes=1) or midpoint["utc"] != start["utc"] + timedelta(seconds=30):
        raise SourceError("Midpoint is not inside the source bracket")
    if any(row["elevation"] is None for row in (start, end, midpoint)):
        return None
    a, b, mid = (Fraction(row["elevation"]) for row in (start, end, midpoint))
    if kind == "rise":
        if not a < THRESHOLD <= b or not a < mid < b:
            raise SourceError("Midpoint fails rising bracket monotonicity check")
        later = mid <= THRESHOLD
    elif kind == "set":
        if not a > THRESHOLD >= b or not a > mid > b:
            raise SourceError("Midpoint fails setting bracket monotonicity check")
        later = mid >= THRESHOLD
    else:
        raise SourceError("Unknown event kind")
    return end["utc"] if later else start["utc"]


def sample_record(row, zone):
    az, el = row["azimuth"], row["elevation"]
    status = "source_missing" if az is None or el is None else (
        "below_horizon" if el <= 0 else "calculated")
    tick = bearing_tick(az) if status == "calculated" else None
    return {"utc": row["utc"].isoformat(), "fixed_local": row["utc"].astimezone(zone).isoformat(),
            "source_azimuth_deg": str(az) if az is not None else None,
            "source_elevation_deg": str(el) if el is not None else None,
            "bearing_15_deg": tick, "strip_cell": tick // 15 if tick is not None else None,
            "status": status}


def extract(packet=PACKET):
    data_dir = packet / "data"
    manifest = json.loads((data_dir / "manifest.json").read_text())
    if manifest["schema_version"] != 1 or manifest["status"] != "draft-review-only":
        raise SourceError("Unreviewed manifest schema/status")
    if manifest["bearing_rounding"] != {
        "cell_degrees": 15, "tie": "half up (clockwise), then modulo 360",
        "input_precision": "Use full six-decimal provider text without intermediate rounding."}:
        raise SourceError("Unreviewed bearing rounding convention")
    if manifest["source_kind"] != "calculated_ephemeris_not_observation" or manifest["target"] != "Sun (10)" or manifest["ephemeris"] != "DE441":
        raise SourceError("Unreviewed source kind, target or ephemeris")
    if manifest["sample_local_times"] != ["09:00", "11:00", "13:00", "15:00"]:
        raise SourceError("This packet's task keys require the frozen sample times and order")
    if list(manifest["sites"]) != ["greenwich", "sydney"] or manifest["dates"] != ["2026-06-21", "2026-12-21"]:
        raise SourceError("Unreviewed packet site/date scope")
    if manifest["horizon_threshold"]["rounding_tie"] != "later minute" or manifest["horizon_threshold"]["unit"] != "degrees":
        raise SourceError("Unreviewed event rounding convention")
    if manifest["horizon_threshold"]["numerator"] != -5 or manifest["horizon_threshold"]["denominator"] != 6:
        raise SourceError("Unreviewed horizon threshold")
    sources = {}
    for entry in manifest["sources"]:
        key = (entry["site_id"], entry["local_date"], entry["kind"])
        if key in sources:
            raise SourceError("Duplicate source receipt")
        sources[key] = (entry, *read_source(data_dir, manifest, entry))
    wanted = {(site, day, kind) for site in manifest["sites"] for day in manifest["dates"] for kind in ("minute", "midpoints")}
    if set(sources) != wanted:
        raise SourceError("Missing or unexpected source series")
    series = []
    for site_id, site in manifest["sites"].items():
        zone = fixed_zone(site["fixed_utc_offset_minutes"])
        for day in manifest["dates"]:
            entry, header, rows = sources[(site_id, day, "minute")]
            mid_entry, _, mid_rows = sources[(site_id, day, "midpoints")]
            by_time = {r["utc"]: r for r in rows}
            mid_by_time = {r["utc"]: r for r in mid_rows}
            selected = []
            for hhmm in manifest["sample_local_times"]:
                local = local_midnight(day, site["fixed_utc_offset_minutes"]) + timedelta(minutes=parse_time(hhmm))
                selected.append(sample_record(by_time[local.astimezone(UTC)], zone))
            brackets = crossing_brackets(rows)
            events = []
            if brackets["status"] == "complete":
                for kind, a, b in brackets["events"]:
                    middle = mid_by_time.get(a["utc"] + timedelta(seconds=30))
                    if middle is None:
                        raise SourceError("Missing matching source midpoint")
                    rounded = rounded_event(kind, a, b, middle)
                    if rounded is None:
                        raise SourceError("Missing elevation at required midpoint")
                    events.append({"kind": kind, "utc": rounded.isoformat(),
                                   "fixed_local": rounded.astimezone(zone).isoformat(),
                                   "time": rounded.astimezone(zone).strftime("%H:%M"),
                                   "bracket_utc": [a["utc"].isoformat(), b["utc"].isoformat()],
                                   "bracket_elevation_deg": [str(a["elevation"]), str(b["elevation"])],
                                   "midpoint_utc": middle["utc"].isoformat(),
                                   "midpoint_elevation_deg": str(middle["elevation"]),
                                   "midpoint_source_id": mid_entry["id"]})
            rise, setting = (events[0]["time"], events[1]["time"]) if events else (None, None)
            eop = re.search(r"EOP coverage\s*:\s*([^\n]+)", header)
            series.append({"id": site_id + "-" + day, "site_id": site_id,
                           "local_date": day, "fixed_utc_offset_minutes": site["fixed_utc_offset_minutes"],
                           "source_id": entry["id"], "raw_row_count": len(rows),
                           "eop_coverage": eop[1].strip() if eop else None,
                           "sunrise": rise, "sunset": setting,
                           "duration_minutes_from_displayed_events": daylight_minutes(rise, setting),
                           "event_status": brackets["status"], "events": events, "samples": selected})
    return {"schema_version": 1, "status": "draft-review-only", "source_kind": "calculated_not_observed",
            "event_method": "Author-derived -50 arcminute center crossing, nearest minute by source midpoint",
            "sources_verified": len(sources), "source_rows": sum(len(s[2]) for s in sources.values()),
            "series": series}


def learner_records(derived):
    """Projection with deliberate omissions; never leak hidden values as hints."""
    projected = {"schema_version": 1, "status": "draft-review-only", "daylight": [], "bearings": []}
    for series in derived["series"]:
        projected["daylight"].append({key: series[key] for key in (
            "id", "site_id", "local_date", "fixed_utc_offset_minutes", "sunrise", "sunset")})
        samples = copy.deepcopy(series["samples"])
        for sample in samples:
            if sample["status"] != "calculated":
                for key in ("source_azimuth_deg", "source_elevation_deg", "bearing_15_deg", "strip_cell"):
                    sample[key] = None
            if sample["status"] == "calculated" and series["id"] == "greenwich-2026-12-21" and "T11:00:" in sample["fixed_local"]:
                for key in ("source_azimuth_deg", "source_elevation_deg", "bearing_15_deg", "strip_cell"):
                    sample[key] = None
                sample["status"] = "author_withheld_for_practice"
        projected["bearings"].append({"id": series["id"], "samples": samples})
    control = copy.deepcopy(next(row for row in projected["daylight"] if row["id"] == "greenwich-2026-12-21"))
    control.update({"id": "M1", "sunset": None, "sunset_status": "author_withheld_for_practice",
                    "scope": "Use only this deliberately incomplete copy for C6; the full source record is available separately."})
    projected["missing_event_control"] = control
    return projected


def answers(derived):
    rows = {s["id"]: s for s in derived["series"]}
    g_j, g_d = rows["greenwich-2026-06-21"], rows["greenwich-2026-12-21"]
    s_j, s_d = rows["sydney-2026-06-21"], rows["sydney-2026-12-21"]
    duration = lambda s: s["duration_minutes_from_displayed_events"]
    ticks = [s["bearing_15_deg"] for s in g_j["samples"]]
    return {"C1": {"kind": "calculated_prediction", "observation": False},
            "C2": {"minutes": duration(g_j), "hours_minutes": list(divmod(duration(g_j), 60))},
            "C3": {"minutes": duration(g_d), "june_minus_december_minutes": duration(g_j) - duration(g_d)},
            "C4": {"june_minutes": duration(s_j), "december_minutes": duration(s_d), "december_minus_june_minutes": duration(s_d) - duration(s_j)},
            "C5": {s["id"]: duration(s) for s in derived["series"]},
            "C6": {"duration_from_M1_only": None, "reason": "author_withheld_sunset"},
            "C7": {"rounded_bearings": [ticks[0], ticks[2]], "strip_cells": [ticks[0] // 15, ticks[2] // 15]},
            "C8": {"paper_marker_clockwise_degrees": int(circular_difference(345, 30)), "cells": 3, "kind": "synthetic_control"},
            "C9": {"missing_time": "11:00", "direction_from_presented_samples": None},
            "C10": {"clockwise_changes_degrees": [int(circular_difference(ticks[0], ticks[1])), int(circular_difference(ticks[1], ticks[2]))], "equal_time_gap_minutes": 120, "equal_changes": False},
            "C11": {"statement_classifications": ["calculated_source_result", "packet_representation_choice", "unsupported", "unsupported", "model_assumption"],
                    "ephemeris_source_result": "calculated", "level_horizon": "model_assumption", "eyewitness_observation": "not_provided"},
            "C12": {"required": ["site", "date", "fixed_clock", "two_shown_time_bearing_pairs", "rounded_values",
                                  "calculated_not_observed", "missing_value_limit", "complete_path_not_established", "no_causal_claim_from_samples"]}}


def compare_usno(derived, packet=PACKET):
    """Check a disclosed transcription of published numerical Greenwich data."""
    manifest = json.loads((packet / "data/manifest.json").read_text())
    pin = manifest["independent_comparison"]
    if pin["event_tolerance_minutes"] != 1:
        raise SourceError("Unreviewed provider comparison tolerance")
    excerpt = json.loads(pinned_file(packet / "data", pin["path"], pin["sha256"]))
    url = urlsplit(excerpt["url"])
    query = parse_qs(url.query)
    expected = {"lat": ["51.4769"], "lon": ["0.0000"], "year": ["2026"], "tz": ["0"], "task": ["0"]}
    if url.netloc != "aa.usno.navy.mil" or any(query.get(k) != v for k, v in expected.items()):
        raise SourceError("Wrong independent-comparison reference")
    tokens = excerpt["source_row_21"].split()
    if len(tokens) != 25 or tokens[0] != "21" or not all(re.fullmatch(r"\d{4}", t) for t in tokens[1:]):
        raise SourceError("Malformed USNO factual row transcription")
    selected = {r["date"]: r for r in excerpt["selected_records"]}
    checks = []
    for month in (6, 12):
        day = f"2026-{month:02d}-21"
        row = next(s for s in derived["series"] if s["id"] == "greenwich-" + day)
        values = tokens[1 + (month - 1) * 2: 3 + (month - 1) * 2]
        for label, value in zip(("sunrise", "sunset"), values):
            hhmm = value[:2] + ":" + value[2:]
            if selected[day][label] != hhmm:
                raise SourceError("USNO selected value disagrees with transcribed source row")
            delta = parse_time(row[label]) - parse_time(hhmm)
            if abs(delta) > pin["event_tolerance_minutes"]:
                raise SourceError("Independent Greenwich event comparison exceeds one minute")
            checks.append({"date": day, "event": label, "jpl_derived_fixed_utc_time": row[label],
                           "usno_published_UT_time": hhmm, "displayed_minute_difference": delta})
        if selected[day]["duration_from_displayed_minutes"] != daylight_minutes(selected[day]["sunrise"], selected[day]["sunset"]):
            raise SourceError("USNO excerpt interval arithmetic disagrees")
    return {"scope": "Four Greenwich event labels only; no second-provider Sydney or bearing data",
            "capture_kind": excerpt["capture_method"], "source_url": excerpt["url"],
            "time_scale_caveat": excerpt["time_scale"], "tolerance_minutes": 1,
            "observational_validation": False, "checks": checks}


def records_markdown(projected):
    names = {"greenwich": "Greenwich", "sydney": "Sydney Observatory Hill"}
    control = projected["missing_event_control"]
    lines = ["# Solar companion records - learner copy", "",
             "**Draft for review; not teaching-ready. Calculated predictions, not observations.**", "",
             "Use these records indoors. Do not look directly at the Sun, with your eyes or through any instrument. No outdoor observation is part of this packet.", "",
             "## Read the labels first", "",
             "These public reference points are not learner locations. Greenwich uses a selected reference near the public observatory; Sydney uses the weather bureau's rounded Observatory Hill reference coordinates. They are calculation inputs, not a claim about a telescope or a person's address.", "",
             "All dates are in 2026. Greenwich uses a fixed UTC+00:00 clock. Sydney uses a fixed UTC+10:00 clock. Neither clock changes for daylight saving. These packet clocks need not match a visitor's local summer clock. Times use a 24-hour clock: 15:00 means three in the afternoon.", "",
             "The June and December dates let us compare two parts of the year. They do not by themselves identify the longest or shortest day of a whole year.", "",
             "NASA/JPL calculates the Sun's position. The packet author then finds sunrise and sunset under a stated standard, level-horizon model and rounds each event to the nearest minute. The interval you calculate is the difference between these displayed times. Actual weather, hills and viewing height can change what is seen.", "",
             "## Daylight ledger", "",
             "| Record | Public reference | Date | Fixed clock | Sunrise | Sunset |",
             "| --- | --- | --- | --- | --- | --- |"]
    for r in projected["daylight"]:
        clock = "UTC+00:00" if r["site_id"] == "greenwich" else "UTC+10:00"
        lines.append(f"| {r['id']} | {names[r['site_id']]} | {r['local_date']} | {clock} | {r['sunrise']} | {r['sunset']} |")
    lines += ["", "### M1 - deliberately incomplete practice copy", "",
              "For C6, use only this card. Its sunset was deliberately removed by the author. The source service did not fail; the full record exists elsewhere. A missing value is not zero.", "",
              "| Card | Public reference | Date | Fixed clock | Sunrise | Sunset |",
              "| --- | --- | --- | --- | --- | --- |",
              f"| M1 | Greenwich | {control['local_date']} | UTC+00:00 | {control['sunrise']} | unknown - deliberately withheld |", "",
              "## Direction scale", "",
              "Bearing names a direction along the horizon, not height or distance. True north is 0 degrees, east 90, south 180 and west 270. Values increase clockwise on a map seen from above. A compass needle is not the definition of true north. 360 and 0 name the same direction.", "",
              "Use a strip with 24 cells. Each cell is 15 degrees; cell 24 repeats cell 0. A blank strip or tactile labeled markers work equally well. The listed strip bearing is the nearest 15-degree mark. At an exact halfway value, choose the next clockwise mark; 360 becomes 0. Round the full source number once.", "",
              "The full decimal column lets you check the rounding. Read it as 'about' that number of degrees; six printed decimal places are not a claim that a person could measure that precisely. Oral, large-print and tactile work may use the same labeled values.", "",
              "## Time-indexed bearings", "",
              "These are selected calculated directions of the Sun's center. Only samples confirmed above the model's horizon receive numerical learner directions. The strip does not draw the full path between samples. Missing-source, below-horizon and deliberately withheld values are labeled differently.", ""]
    for table in projected["bearings"]:
        site_id, day = table["id"].split("-", 1)
        clock = "UTC+00:00" if site_id == "greenwich" else "UTC+10:00"
        lines += [f"### {names[site_id]} - {day} ({clock})", "",
                  "| Packet time | Source bearing, degrees | Rounded strip bearing, degrees |",
                  "| --- | --- | --- |"]
        for sample in table["samples"]:
            hhmm = datetime.fromisoformat(sample["fixed_local"]).strftime("%H:%M")
            if sample["status"] == "calculated":
                az, tick = sample["source_azimuth_deg"], str(sample["bearing_15_deg"])
            else:
                labels = {"author_withheld_for_practice": "unknown - deliberately withheld",
                          "source_missing": "unknown - source value unavailable",
                          "below_horizon": "excluded - center at or below model horizon"}
                if sample["status"] not in labels:
                    raise SourceError("Unreviewed learner missing-data status")
                az, tick = labels[sample["status"]], "unknown"
            lines.append(f"| {hhmm} | {az} | {tick} |")
        lines.append("")
    lines += ["## Task pointers", "",
              "C7 uses Greenwich June 09:00 and 13:00. C9 uses Greenwich December, including its withheld 11:00 entry. C10 uses the complete Greenwich June series at 09:00, 11:00 and 13:00.", "",
              "Sydney's June strip values go 45, 15, 345, 315. The short endpoint turns decrease through north. The numbers need not always increase with time. Sparse samples alone do not prove the complete path or its cause.", "",
              "At Sydney, 09:00 on June 21 in this packet is 23:00 UTC on June 20. A clock conversion can change the date; it does not move the Sun. Use the packet clock when answering.", "",
              "## Source credit", "",
              "Calculated position data: [NASA/JPL Horizons](https://ssd.jpl.nasa.gov/horizons/), retrieved November 26, 2026. Standard sunrise/set convention: [U.S. Naval Observatory](https://aa.usno.navy.mil/faq/RST_defs). Sydney reference: [Australian Bureau of Meteorology station 066062](https://www.bom.gov.au/climate/averages/tables/cw_066062_SiteMap.shtml). The packet's event extraction, rounding and deliberate omissions are the author's modifications. These providers have not endorsed this curriculum.", "",
              "June values are calculations about an earlier date. December 21 was still in the future when the data were retrieved. Neither kind is an eyewitness observation.", ""]
    return "\n".join(lines)


def generated_files(packet=PACKET):
    result = extract(packet)
    if any(s["event_status"] != "complete" or any(r["status"] != "calculated" for r in s["samples"]) for s in result["series"]):
        raise SourceError("Selected packet source data are incomplete or below horizon; no answer set generated")
    learner = learner_records(result)
    return {"data/ephemerides.json": dumps(result), "data/learner-records.json": dumps(learner),
            "data/answers.json": dumps(answers(result)), "data/source-comparison.json": dumps(compare_usno(result, packet)),
            "records.md": records_markdown(learner)}


def fetch_review_copy(packet, output):
    """Explicit online acquisition; sequential, bounded backoff, immutable pins."""
    if output.exists():
        raise SourceError("Use a new output directory; existing snapshots are never overwritten")
    extract(packet)  # Validate the pinned endpoint/requests before any network call.
    manifest = json.loads((packet / "data/manifest.json").read_text())
    output.mkdir(parents=True)
    receipts = []
    for entry in manifest["sources"]:
        metadata_bytes = pinned_file(packet / "data", entry["request_path"], entry["request_sha256"])
        meta = json.loads(metadata_bytes)
        request = Request(meta["request_url"], headers={"User-Agent": "SchoolOps-Solar-Review/1.0 (+https://github.com/larsbx/school-ops/issues)", "Accept": "application/json"})
        for attempt in range(3):
            try:
                with urlopen(request, timeout=30) as response:
                    raw = response.read(2_000_001)
                    if len(raw) > 2_000_000:
                        raise SourceError("Unexpectedly large provider response")
                    headers = dict(response.headers.items())
                break
            except HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise SourceError(f"Source unavailable: HTTP {exc.code}; frozen data unchanged") from exc
                time.sleep(2 ** (attempt + 1))
            except (URLError, TimeoutError) as exc:
                if attempt == 2:
                    raise SourceError("Source unavailable; frozen data unchanged") from exc
                time.sleep(2 ** (attempt + 1))
        parse_horizons(raw)
        name = entry["id"] + ".json"
        (output / name).write_bytes(raw)
        receipts.append({"id": entry["id"], "file": name, "sha256": digest(raw),
                         "retrieved_at_utc": datetime.now(UTC).isoformat(), "request_url": meta["request_url"],
                         "parameters": meta["parameters"], "response_headers": headers,
                         "status": "new_response_requires_review_not_admitted"})
        (output / "receipts.json").write_text(dumps(receipts))
    return {"responses_fetched": len(receipts), "admitted": False, "output": str(output)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "build", "fetch"), nargs="?", default="verify")
    parser.add_argument("--packet", type=Path, default=PACKET)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "fetch":
            if args.output is None:
                parser.error("fetch requires --output NEW_DIRECTORY")
            print(dumps(fetch_review_copy(args.packet, args.output)), end="")
            return 0
        generated = generated_files(args.packet)
        if args.command == "build":
            if args.output is None:
                parser.error("build requires --output DIRECTORY")
            for name, body in generated.items():
                dest = args.output / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(body, encoding="utf-8")
        else:
            for name, body in generated.items():
                if (args.packet / name).read_text(encoding="utf-8") != body:
                    raise SourceError("Derived artifact differs from pinned source extraction: " + name)
        data = json.loads(generated["data/ephemerides.json"])
        print(dumps({"status": "PASS", "operation": args.command, "source_responses": data["sources_verified"],
                     "source_rows": data["source_rows"], "daylight_intervals": len(data["series"]),
                     "bearing_samples": sum(len(s["samples"]) for s in data["series"]),
                     "midpoint_rounding_checks": sum(len(s["events"]) for s in data["series"]),
                     "usno_greenwich_event_comparisons": 4,
                     "teaching_approval": False}), end="")
        return 0
    except (SourceError, KeyError, OSError, ValueError) as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
