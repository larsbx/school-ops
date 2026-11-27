"""Offline source, numerical, omission and learner/key checks for the solar draft.

Expected event labels and bearings below were independently read from the
captured JPL rows and midpoint queries. These tests do not certify physical
accuracy, a continuous sky path, accessibility in use, or teaching readiness.
"""
from __future__ import annotations

import copy
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from tools import solar_ephemeris as solar


PACKET = solar.PACKET
EXPECTED = {
    "greenwich-2026-06-21": {
        "events": ("03:43", "20:21"), "minutes": 998,
        "azimuths": ("111.371720", "151.171667", "207.264056", "247.702028"),
        "ticks": (105, 150, 210, 255),
    },
    "greenwich-2026-12-21": {
        "events": ("08:03", "15:53"), "minutes": 470,
        "azimuths": ("139.751240", "166.293650", "194.607631", "221.047584"),
        "ticks": (135, 165, 195, 225),
    },
    "sydney-2026-06-21": {
        "events": ("07:00", "16:54"), "minutes": 594,
        "azimuths": ("42.563605", "15.264261", "343.123321", "316.253770"),
        "ticks": (45, 15, 345, 315),
    },
    "sydney-2026-12-21": {
        "events": ("04:41", "19:05"), "minutes": 864,
        "azimuths": ("86.161982", "51.488440", "301.078467", "271.726203"),
        "ticks": (90, 45, 300, 270),
    },
}


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def table_transform(result, transform):
    before, rest = result.split("$$SOE")
    body, after = rest.split("$$EOE")
    lines = body.strip().splitlines()
    return before + "$$SOE\n" + "\n".join(transform(lines)) + "\n$$EOE" + after


def replace_cell(lines, row, column, value):
    altered = list(lines)
    fields = next(csv.reader([altered[row]]))
    fields[column] = value
    altered[row] = ",".join(fields)
    return altered


def teacher_sections(text):
    parts = re.split(r"^### C(\d+)\b[^\n]*\n", text, flags=re.MULTILINE)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}


class SolarSourceRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.derived = solar.extract()
        cls.series = {row["id"]: row for row in cls.derived["series"]}

    def test_known_source_results_and_all_sixteen_ticks(self):
        self.assertEqual(8, self.derived["sources_verified"])
        self.assertEqual(5772, self.derived["source_rows"])
        self.assertEqual(set(EXPECTED), set(self.series))
        for key, expected in EXPECTED.items():
            with self.subTest(series=key):
                row = self.series[key]
                self.assertEqual(expected["events"], (row["sunrise"], row["sunset"]))
                self.assertEqual(expected["minutes"], row["duration_minutes_from_displayed_events"])
                self.assertEqual(expected["azimuths"], tuple(s["source_azimuth_deg"] for s in row["samples"]))
                self.assertEqual(expected["ticks"], tuple(s["bearing_15_deg"] for s in row["samples"]))
                self.assertEqual(tuple(x // 15 for x in expected["ticks"]), tuple(s["strip_cell"] for s in row["samples"]))
                self.assertEqual(1441, row["raw_row_count"])
                self.assertEqual("complete", row["event_status"])
                self.assertTrue(all(s["status"] == "calculated" and Decimal(s["source_elevation_deg"]) > 0 for s in row["samples"]))

    def test_raw_csv_samples_independently_match_derived_values(self):
        for key, expected in EXPECTED.items():
            with self.subTest(series=key):
                raw = json.loads((PACKET / "data/raw" / (key + "-minute.json")).read_bytes())
                body = raw["result"].split("$$SOE")[1].split("$$EOE")[0]
                rows = {fields[0].strip(): fields for fields in csv.reader(body.strip().splitlines())}
                for sample, known in zip(self.series[key]["samples"], expected["azimuths"]):
                    stamp = datetime.fromisoformat(sample["utc"]).strftime("%Y-%b-%d %H:%M:%S")
                    self.assertEqual(known, rows[stamp][3].strip())
                    self.assertEqual(sample["source_elevation_deg"], rows[stamp][4].strip())

    def test_all_five_generated_artifacts_reproduce_exact_bytes_without_network(self):
        with patch.object(solar, "urlopen", side_effect=AssertionError("Offline build used network")):
            generated = solar.generated_files()
        self.assertEqual({"data/ephemerides.json", "data/learner-records.json", "data/answers.json", "data/source-comparison.json", "records.md"}, set(generated))
        for name, body in generated.items():
            with self.subTest(artifact=name):
                self.assertEqual((PACKET / name).read_bytes(), body.encode("utf-8"))

    def test_midpoint_queries_choose_known_event_labels_without_interpolation(self):
        threshold = Fraction(-5, 6)
        for key, row in self.series.items():
            for event, known in zip(row["events"], EXPECTED[key]["events"]):
                with self.subTest(series=key, event=event["kind"]):
                    left, right = map(datetime.fromisoformat, event["bracket_utc"])
                    middle = datetime.fromisoformat(event["midpoint_utc"])
                    self.assertEqual(timedelta(minutes=1), right - left)
                    self.assertEqual(left + timedelta(seconds=30), middle)
                    middle_elevation = Fraction(event["midpoint_elevation_deg"])
                    use_right = middle_elevation <= threshold if event["kind"] == "rise" else middle_elevation >= threshold
                    self.assertEqual(right if use_right else left, datetime.fromisoformat(event["utc"]))
                    self.assertEqual(known, event["time"])

    def test_fixed_sydney_clock_preserves_previous_utc_date(self):
        for month in ("06", "12"):
            sample = self.series[f"sydney-2026-{month}-21"]["samples"][0]
            self.assertEqual(f"2026-{month}-20T23:00:00+00:00", sample["utc"])
            self.assertEqual(f"2026-{month}-21T09:00:00+10:00", sample["fixed_local"])
            midnight = solar.local_midnight(f"2026-{month}-21", 600).astimezone(timezone.utc)
            self.assertEqual(f"2026-{month}-20T14:00:00+00:00", midnight.isoformat())

    def test_original_synthetic_records_are_byte_identical_to_base(self):
        # SHA-256 independently taken from git show 2aa3eb3a...:.../records.md.
        original = PACKET.parent / "records.md"
        self.assertEqual("0039734795fe4d4d08e9655986977894dbde6b0bf9746868242ff9a17b567b5c", sha256(original.read_bytes()))
        self.assertIn("All entries are invented", original.read_text(encoding="utf-8"))

    def test_projection_keeps_omissions_without_deleting_provenance(self):
        projected = solar.learner_records(self.derived)
        december = next(x for x in projected["bearings"] if x["id"] == "greenwich-2026-12-21")
        omitted = december["samples"][1]
        self.assertEqual("author_withheld_for_practice", omitted["status"])
        for key in ("source_azimuth_deg", "source_elevation_deg", "bearing_15_deg", "strip_cell"):
            self.assertIsNone(omitted[key])
        self.assertEqual("166.293650", self.series["greenwich-2026-12-21"]["samples"][1]["source_azimuth_deg"])
        control = projected["missing_event_control"]
        self.assertIsNone(control["sunset"])
        self.assertNotIn("duration_minutes_from_displayed_events", control)
        self.assertEqual("author_withheld_for_practice", control["sunset_status"])
        learner_text = (PACKET / "learner.md").read_text() + (PACKET / "records.md").read_text()
        self.assertNotIn("166.293650", learner_text)
        self.assertNotIn("### C2", learner_text)  # Teacher solution heading never included.

    def test_data_status_does_not_assert_observation_or_teaching_approval(self):
        self.assertEqual("draft-review-only", self.derived["status"])
        self.assertEqual("calculated_not_observed", self.derived["source_kind"])
        key = solar.answers(self.derived)
        self.assertFalse(key["C1"]["observation"])
        self.assertIsNone(key["C6"]["duration_from_M1_only"])
        self.assertIsNone(key["C9"]["direction_from_presented_samples"])

    def test_usno_comparison_has_only_four_greenwich_events(self):
        comparison = solar.compare_usno(self.derived)
        self.assertEqual(4, len(comparison["checks"]))
        self.assertEqual({("2026-06-21", "sunrise"), ("2026-06-21", "sunset"),
                          ("2026-12-21", "sunrise"), ("2026-12-21", "sunset")},
                         {(row["date"], row["event"]) for row in comparison["checks"]})
        self.assertTrue(all(row["displayed_minute_difference"] == 0 for row in comparison["checks"]))
        self.assertFalse(comparison["observational_validation"])
        self.assertIn("no second-provider Sydney or bearing data", comparison["scope"])
        self.assertIn("not an HTTP response capture", comparison["capture_kind"])
        self.assertIn("UT1", comparison["time_scale_caveat"])

    def test_projection_and_renderer_hide_unusable_numbers_and_keep_statuses(self):
        for az, elevation, status, label in ((None, Decimal("18.930570"), "source_missing", "unknown - source value unavailable"),
                                            (Decimal("42.563605"), None, "source_missing", "unknown - source value unavailable"),
                                            (Decimal("42.563605"), Decimal("-5"), "below_horizon", "excluded - center at or below model horizon")):
            with self.subTest(status=status, azimuth=az):
                changed = copy.deepcopy(self.derived)
                series = next(row for row in changed["series"] if row["id"] == "sydney-2026-06-21")
                original = series["samples"][0]
                series["samples"][0] = solar.sample_record({"utc": datetime.fromisoformat(original["utc"]), "azimuth": az, "elevation": elevation}, solar.fixed_zone(600))
                projected = solar.learner_records(changed)
                result = next(row for row in projected["bearings"] if row["id"] == series["id"])["samples"][0]
                self.assertEqual(status, result["status"])
                for key in ("source_azimuth_deg", "source_elevation_deg", "bearing_15_deg", "strip_cell"):
                    self.assertIsNone(result[key])
                rendered = solar.records_markdown(projected)
                self.assertIn(f"| 09:00 | {label} | unknown |", rendered)
                self.assertNotIn("42.563605", rendered)


class SolarMathAndMissingDataTests(unittest.TestCase):
    def test_rounding_boundaries_and_no_double_rounding(self):
        controls = {"0": 0, "7.499999": 0, "7.5": 15, "112.499999": 105,
                    "112.5": 120, "247.49": 240, "247.5": 255,
                    "352.499999": 345, "352.5": 0, "359.999999": 0, "360": 0}
        for value, expected in controls.items():
            with self.subTest(value=value):
                self.assertEqual(expected, solar.bearing_tick(value))
        for cell in range(24):
            with self.subTest(halfway=cell):
                self.assertEqual(((cell + 1) % 24) * 15, solar.bearing_tick(str(Decimal(cell * 15) + Decimal("7.5"))))
        self.assertIsNone(solar.bearing_tick(None))

    def test_nonfinite_invalid_and_boolean_values_are_not_solar_numbers(self):
        for bad in ("NaN", "sNaN", "Infinity", "-Infinity", "not available", True, False):
            with self.subTest(value=bad), self.assertRaises(solar.SourceError):
                solar.decimal(bad)
        for bad in ("-0.0001", "360.0001", "NaN", True):
            with self.subTest(bearing=bad), self.assertRaises(solar.SourceError):
                solar.bearing_tick(bad)
        for missing in (None, "", "  ", "n.a."):
            self.assertIsNone(solar.decimal(missing, allow_missing=True))

    def test_daylight_arithmetic_and_missing_or_cross_day_rejection(self):
        self.assertEqual(998, solar.daylight_minutes("03:43", "20:21"))
        self.assertEqual(470, solar.daylight_minutes("08:03", "15:53"))
        self.assertIsNone(solar.daylight_minutes("08:03", None))
        self.assertIsNone(solar.daylight_minutes(None, "15:53"))
        for start, end in (("23:00", "01:00"), ("08:00", "08:00"), ("25:00", "26:00"), ("8:00", "15:00"), ("08:60", "15:00")):
            with self.subTest(interval=(start, end)), self.assertRaises(solar.SourceError):
                solar.daylight_minutes(start, end)

    def test_direction_is_explicit_and_wrap_is_not_assumed_solar_motion(self):
        self.assertEqual(45, solar.circular_difference(345, 30, "clockwise"))
        self.assertEqual(330, solar.circular_difference(15, 345, "clockwise"))
        self.assertEqual(30, solar.circular_difference(15, 345, "counterclockwise"))
        self.assertEqual(0, solar.circular_difference(0, 360))
        self.assertIsNone(solar.circular_difference(None, 30))
        with self.assertRaises(solar.SourceError):
            solar.circular_difference(15, 345, "shortest")

    def test_missing_and_below_horizon_are_distinct_from_authored_omissions(self):
        stamp = datetime(2026, 6, 21, 0, tzinfo=timezone.utc)
        for az, elevation, status in ((None, Decimal("5"), "source_missing"),
                                      (Decimal("180"), None, "source_missing"),
                                      (Decimal("180"), Decimal("-5"), "below_horizon"),
                                      (Decimal("180"), Decimal("0"), "below_horizon")):
            with self.subTest(az=az, elevation=elevation):
                sample = solar.sample_record({"utc": stamp, "azimuth": az, "elevation": elevation}, timezone.utc)
                self.assertEqual(status, sample["status"])
                self.assertIsNone(sample["bearing_15_deg"])
                self.assertIsNone(sample["strip_cell"])

    def test_incomplete_event_series_never_fills_a_daylight_duration(self):
        stamp = datetime(2026, 6, 21, 0, tzinfo=timezone.utc)
        base = [{"utc": stamp + timedelta(minutes=i), "elevation": Decimal("10"), "azimuth": Decimal("90")} for i in range(5)]
        missing = copy.deepcopy(base)
        missing[2]["elevation"] = None
        self.assertEqual({"status": "source_missing", "events": []}, solar.crossing_brackets(missing))
        gapped = base[:2] + base[3:]
        self.assertEqual({"status": "source_incomplete", "events": []}, solar.crossing_brackets(gapped))
        self.assertEqual({"status": "no_unique_rise_set_pair", "events": []}, solar.crossing_brackets(base))

    def test_midpoint_direction_ties_and_invalid_brackets(self):
        stamp = datetime(2026, 6, 21, 0, tzinfo=timezone.utc)
        def row(seconds, elevation):
            return {"utc": stamp + timedelta(seconds=seconds), "elevation": elevation}
        for kind, start, end, earlier, later in (("rise", Decimal("-1"), Decimal("-.6"), Decimal("-.7"), Decimal("-.9")),
                                                ("set", Decimal("-.6"), Decimal("-1"), Decimal("-.9"), Decimal("-.7"))):
            with self.subTest(kind=kind):
                a, b = row(0, start), row(60, end)
                self.assertEqual(stamp, solar.rounded_event(kind, a, b, row(30, earlier)))
                self.assertEqual(stamp + timedelta(minutes=1), solar.rounded_event(kind, a, b, row(30, later)))
                self.assertEqual(stamp + timedelta(minutes=1), solar.rounded_event(kind, a, b, row(30, Fraction(-5, 6))))
                self.assertIsNone(solar.rounded_event(kind, a, b, row(30, None)))
                with self.assertRaises(solar.SourceError):
                    solar.rounded_event(kind, a, b, row(29, earlier))
                with self.assertRaises(solar.SourceError):
                    solar.rounded_event(kind, a, b, row(30, Decimal("30")))

    def test_fractional_timestamps_and_invalid_clocks(self):
        self.assertEqual(datetime(2026, 6, 21, 3, 42, 30, tzinfo=timezone.utc), solar.parse_epoch("2026-Jun-21 03:42:30.000"))
        for text in ("2026-Jun-31 03:42:30", "2026-Jun-21 24:00:00", "2026-Jun-21 03:42", "2026-XXX-21 03:42:30"):
            with self.subTest(timestamp=text), self.assertRaises(solar.SourceError):
                solar.parse_epoch(text)
        for offset in (True, 10.5, 900, -800):
            with self.subTest(offset=offset), self.assertRaises(solar.SourceError):
                solar.fixed_zone(offset)


class SolarSourceRejectionTests(unittest.TestCase):
    """Re-pin mutations in disposable copies to test semantics beyond hashes."""
    def clone_packet(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        clone = Path(temporary.name) / "packet"
        shutil.copytree(PACKET / "data", clone / "data")
        return clone

    def mutate_source(self, clone, *, result_change=None, metadata_change=None, object_change=None,
                      source_id="greenwich-2026-06-21-minute"):
        data = clone / "data"
        manifest = json.loads((data / "manifest.json").read_text())
        entry = next(x for x in manifest["sources"] if x["id"] == source_id)
        obj = json.loads((data / entry["raw_path"]).read_bytes())
        metadata = json.loads((data / entry["request_path"]).read_bytes())
        if object_change:
            object_change(obj)
        if result_change:
            obj["result"] = result_change(obj["result"])
        raw = (json.dumps(obj) + "\n").encode()
        text = obj["result"].encode()
        entry["raw_sha256"], entry["text_sha256"] = sha256(raw), sha256(text)
        metadata["sha256"] = entry["raw_sha256"]
        if metadata_change:
            metadata_change(metadata)
            metadata["request_url"] = "https://ssd.jpl.nasa.gov/api/horizons.api?" + urlencode(metadata["parameters"])
        request = (json.dumps(metadata) + "\n").encode()
        entry["request_sha256"] = sha256(request)
        (data / entry["raw_path"]).write_bytes(raw)
        (data / entry["text_path"]).write_bytes(text)
        (data / entry["request_path"]).write_bytes(request)
        (data / "manifest.json").write_text(json.dumps(manifest))

    def test_raw_byte_tampering_fails_checksum(self):
        clone = self.clone_packet()
        path = clone / "data/raw/greenwich-2026-06-21-minute.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(solar.SourceError, "checksum"):
            solar.extract(clone)

    def test_saved_text_cannot_diverge_from_raw_response(self):
        clone = self.clone_packet()
        manifest_path = clone / "data/manifest.json"
        manifest = json.loads(manifest_path.read_text())
        first = manifest["sources"][0]
        path = clone / "data" / first["text_path"]
        changed = path.read_bytes() + b"\n"
        path.write_bytes(changed)
        first["text_sha256"] = sha256(changed)
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(solar.SourceError, "Decoded text"):
            solar.extract(clone)

    def test_wrong_target_frame_calendar_refraction_and_time_heading_rejected(self):
        changes = (("Sun (10)", "Moon (301)"), ("ITRF93", "ICRF"),
                   ("NO (AIRLESS)", "YES (REFRACTED)"), ("Gregorian", "Mixed Julian/Gregorian"),
                   ("Date__(UT)", "Date__(TT)"), ("Azi_(a-app)", "Azi_(r-app)"))
        for old, new in changes:
            with self.subTest(change=(old, new)):
                clone = self.clone_packet()
                self.mutate_source(clone, result_change=lambda text, a=old, b=new: text.replace(a, b))
                with self.assertRaises(solar.SourceError):
                    solar.extract(clone)

    def test_unreviewed_api_signature_or_provider_error_rejected(self):
        for mutation in (lambda obj: obj["signature"].update(version="999"), lambda obj: obj.update(error="service unavailable")):
            clone = self.clone_packet()
            self.mutate_source(clone, object_change=mutation)
            with self.assertRaises(solar.SourceError):
                solar.extract(clone)

    def test_wrong_requested_coordinates_or_time_conventions_rejected(self):
        changes = (("SITE_COORD", "'151.21,-33.86,0'"), ("TIME_TYPE", "'TT'"),
                   ("TIME_ZONE", "'+01:00'"), ("APPARENT", "'REFRACTED'"),
                   ("START_TIME", "'2026-06-20 00:00'"), ("STEP_SIZE", "'2 m'"))
        for parameter, value in changes:
            with self.subTest(parameter=parameter):
                clone = self.clone_packet()
                self.mutate_source(clone, metadata_change=lambda meta, k=parameter, v=value: meta["parameters"].update({k: v}))
                with self.assertRaises(solar.SourceError):
                    solar.extract(clone)

    def test_wrong_returned_coordinates_and_receipt_coordinates_rejected(self):
        clone = self.clone_packet()
        self.mutate_source(clone, result_change=lambda text: text.replace("0.0, 51.4769,", "0.0, 52.4769,"))
        with self.assertRaises(solar.SourceError):
            solar.extract(clone)
        clone = self.clone_packet()
        self.mutate_source(clone, metadata_change=lambda meta: meta.update(latitude_deg=52.4769))
        with self.assertRaises(solar.SourceError):
            solar.extract(clone)

    def test_duplicate_gapped_and_wrong_date_samples_rejected(self):
        changes = (lambda lines: lines[:2] + [lines[1]] + lines[2:],
                   lambda lines: lines[:10] + lines[11:],
                   lambda lines: replace_cell(lines, 1, 0, "2026-Jun-21 00:01:30"),
                   lambda lines: [line.replace("2026-Jun-21", "2026-Jun-20") for line in lines])
        for index, change in enumerate(changes):
            with self.subTest(change=index):
                clone = self.clone_packet()
                self.mutate_source(clone, result_change=lambda text, fn=change: table_transform(text, fn))
                with self.assertRaises(solar.SourceError):
                    solar.extract(clone)

    def test_nonfinite_missing_or_below_horizon_selected_samples_not_admitted(self):
        for column, value in ((3, "NaN"), (4, "Infinity"), (3, "n.a."), (4, "n.a."), (4, "-1.000000")):
            with self.subTest(column=column, value=value):
                clone = self.clone_packet()
                self.mutate_source(clone, result_change=lambda text, col=column, val=value: table_transform(text, lambda rows: replace_cell(rows, 9 * 60, col, val)))
                with self.assertRaises(solar.SourceError):
                    solar.generated_files(clone)

    def test_manifest_duplicate_series_threshold_and_scale_mutations_rejected(self):
        mutations = (lambda data: data["sources"].append(copy.deepcopy(data["sources"][0])),
                     lambda data: data["sources"].pop(),
                     lambda data: data["horizon_threshold"].update(numerator=-1),
                     lambda data: data["bearing_rounding"].update(cell_degrees=10),
                     lambda data: data["horizon_threshold"].update(rounding_tie="earlier minute"),
                     lambda data: data["horizon_threshold"].update(unit="radians"),
                     lambda data: data.update(sample_local_times=["09:00", "13:00", "11:00", "15:00"]),
                     lambda data: data.update(sample_local_times=["08:00", "10:00", "12:00", "14:00"]))
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                clone = self.clone_packet()
                path = clone / "data/manifest.json"
                manifest = json.loads(path.read_text())
                mutation(manifest)
                path.write_text(json.dumps(manifest))
                with self.assertRaises(solar.SourceError):
                    solar.extract(clone)

    def test_refresh_cannot_overwrite_existing_snapshot(self):
        with tempfile.TemporaryDirectory() as existing:
            with patch.object(solar, "urlopen", side_effect=AssertionError("Unexpected network call")):
                with self.assertRaisesRegex(solar.SourceError, "new output directory"):
                    solar.fetch_review_copy(PACKET, Path(existing))


class SolarLearnerTeacherAgreementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.derived = solar.extract()
        cls.key = solar.answers(cls.derived)
        cls.teacher = (PACKET / "teacher.md").read_text(encoding="utf-8")
        cls.learner = (PACKET / "learner.md").read_text(encoding="utf-8")
        cls.sections = teacher_sections(cls.teacher)

    def test_every_actual_task_has_a_separate_machine_and_teacher_key(self):
        self.assertEqual(set(range(1, 13)), set(self.sections))
        self.assertEqual(set(range(1, 13)), {int(n) for n in re.findall(r"\*\*C(\d+)\.", self.learner)})
        self.assertEqual({f"C{i}" for i in range(1, 13)}, set(self.key))
        self.assertIn("Teacher only", self.teacher)
        self.assertIn("not approved for teaching", self.teacher)
        self.assertNotIn("Complete answer key", self.learner)

    def test_c2_c3_printed_durations_and_splits_match_source_events(self):
        for task, identifier in ((2, "greenwich-2026-06-21"), (3, "greenwich-2026-12-21")):
            with self.subTest(task=task):
                section = self.sections[task]
                hours, minutes, total = map(int, re.search(r"\*\*(\d+) h (\d+) min = (\d+) min\*\*", section).groups())
                self.assertEqual(EXPECTED[identifier]["minutes"], hours * 60 + minutes)
                self.assertEqual(hours * 60 + minutes, total)
                source_rise, source_set = EXPECTED[identifier]["events"]
                self.assertIn(f"**{source_rise} to {source_set}**", section)
                split = [int(h) * 60 + int(m) for h, m in re.findall(r"is (\d+) h (\d+) min", section)]
                self.assertEqual(2, len(split))
                self.assertEqual(total, sum(split))
                self.assertEqual(self.key[f"C{task}"]["minutes"], total)

    def test_c4_c5_actual_teacher_tables_match_all_four_source_intervals(self):
        c4 = re.findall(r"\| 21 (June|December) 2026 \| (\d\d:\d\d) to (\d\d:\d\d) \| \*\*(\d+) h (\d+) min = (\d+) min\*\* \|", self.sections[4])
        self.assertEqual(2, len(c4))
        for month, rise, setting, h, m, total in c4:
            identifier = "sydney-2026-" + ("06" if month == "June" else "12") + "-21"
            self.assertEqual(EXPECTED[identifier]["events"], (rise, setting))
            self.assertEqual(EXPECTED[identifier]["minutes"], int(total))
            self.assertEqual(int(total), int(h) * 60 + int(m))
        c5 = re.findall(r"\| (Greenwich|Sydney) \| 21 (June|December) 2026 \| \*\*(\d+) min\*\* \|", self.sections[5])
        actual = {site.lower() + "-2026-" + ("06" if month == "June" else "12") + "-21": int(total) for site, month, total in c5}
        self.assertEqual({key: value["minutes"] for key, value in EXPECTED.items()}, actual)
        self.assertEqual(self.key["C5"], actual)
        self.assertIn("528 min = 8 h 48 min", self.sections[5])
        self.assertIn("270 min = 4 h 30 min", self.sections[5])
        self.assertEqual(528, actual["greenwich-2026-06-21"] - actual["greenwich-2026-12-21"])
        self.assertEqual(270, actual["sydney-2026-12-21"] - actual["sydney-2026-06-21"])

    def test_c7_actual_teacher_rounding_table_and_c8_c10_turns(self):
        rows = re.findall(r"\| (\d\d:\d\d) \| ([\d.]+) degrees \| (\d+) and (\d+) \| \*\*(\d+) degrees\*\* \| \*\*(\d+)\*\* \|", self.sections[7])
        self.assertEqual(2, len(rows))
        expected_rows = (("09:00", "111.371720", 105, 120, 105, 7),
                         ("13:00", "207.264056", 195, 210, 210, 14))
        normalized = tuple((time, value, *(int(x) for x in numbers)) for time, value, *numbers in rows)
        self.assertEqual(expected_rows, normalized)
        self.assertEqual([105, 210], self.key["C7"]["rounded_bearings"])
        self.assertEqual([7, 14], self.key["C7"]["strip_cells"])
        self.assertIn("45 degrees = 3 cells", self.sections[8])
        self.assertEqual(45, self.key["C8"]["paper_marker_clockwise_degrees"])
        self.assertEqual("synthetic_control", self.key["C8"]["kind"])
        self.assertIn("150 − 105 = 45 degrees", self.sections[10])
        self.assertIn("210 − 150 = 60 degrees", self.sections[10])
        self.assertEqual([45, 60], self.key["C10"]["clockwise_changes_degrees"])
        self.assertFalse(self.key["C10"]["equal_changes"])

    def test_c6_c9_missing_keys_retain_evidence_limits(self):
        self.assertIn("unknown", self.sections[6])
        self.assertIn("not zero", self.sections[6])
        self.assertIn("not a source failure", self.sections[6])
        self.assertIsNone(self.key["C6"]["duration_from_M1_only"])
        self.assertIn("166.293650", self.sections[9])
        self.assertIn("**165 degrees**", self.sections[9])
        self.assertIn("interpolation", self.sections[9])
        self.assertIsNone(self.key["C9"]["direction_from_presented_samples"])

    def test_c11_all_five_statements_and_c12_rhetoric_are_aligned(self):
        expected = ["calculated_source_result", "packet_representation_choice", "unsupported", "unsupported", "model_assumption"]
        self.assertEqual(expected, self.key["C11"]["statement_classifications"])
        self.assertEqual(5, len(re.findall(r"^\| [1-5]\. ", self.sections[11], re.MULTILINE)))
        for term in ("Calculated source result", "Packet representation choice", "Unsupported", "Model assumption"):
            self.assertIn(term, self.sections[11])
        for term in ("UTC+00:00", "09:00", "13:00", "105", "210", "rounded", "11:00", "cause", "path"):
            self.assertIn(term, self.sections[12])
        required = self.key["C12"]["required"]
        for term in ("two_shown_time_bearing_pairs", "calculated_not_observed", "missing_value_limit", "no_causal_claim_from_samples"):
            self.assertIn(term, required)
        self.assertTrue(any("clock" in term for term in required))
        self.assertTrue(any("round" in term for term in required))
        self.assertTrue(any("path" in term for term in required))


if __name__ == "__main__":
    unittest.main()
