#!/usr/bin/env python3
"""Reject incomplete or duplicated diagnostic evidence before reporting success."""
import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest

from attribution_summary import PHASES, summarize


class SummaryContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="df-motion-summary-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.configuration = {"trials_per_variant": 1, "warmup_frames_per_trial": 1,
                              "batches_per_trial": 1, "frames_per_batch": 1,
                              "viewport_counts": [1], "workload_filter": "idle"}
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({"sites": [{"id": 1, "name": "test.site"}]}), encoding="utf-8")
        self.csv_rows, self.rows = [], []
        for name in ("clock_pair", "empty_scope"):
            self.rows.append({"type": "calibration", "name": name, "samples": 2048,
                              "median_ns": 0, "p95_ns": 0, "p99_ns": 0, "worst_ns": 0})
        for engine, order in (("baseline", 0), ("candidate", 1)):
            self.csv_rows.append({"engine": engine, "workload": "idle", "viewports": 1,
                                  "trial": 0, "order": order, "batch": 0, "frame": 0,
                                  "allocations": 0, "allocated_bytes": 0, "retained_bytes": 0})
            for kind, frame in (("warmup", -1), ("frame", 0), ("teardown", 1)):
                for identifier, phase in enumerate(PHASES):
                    row = {"type": "phase", "engine": engine, "workload": "idle", "viewports": 1,
                           "trial": 0, "order": order, "frame": frame, "kind": kind,
                           "id": identifier, "phase": phase, "size_histogram": [],
                           "allocation_phase_counts": [0]*12, "free_phase_counts": [0]*12}
                    for field in ("inclusive_ns", "exclusive_ns", "calls", "allocations", "requested_bytes",
                                  "backing_bytes", "frees", "freed_bytes", "malloc_ns", "free_ns", "live_bytes",
                                  "peak_live_bytes", "lifetimes", "same_frame_frees", "lifetime_frames_max",
                                  "lifetime_ns_sum", "lifetime_ns_min", "lifetime_ns_max"):
                        row[field] = 0
                    self.rows.append(row)

    def run_summary(self, rows=None, csv_rows=None, suffix=""):
        raw = self.root / "raw.jsonl"
        raw.write_text("".join(json.dumps(row)+"\n" for row in (self.rows if rows is None else rows))+suffix,
                       encoding="utf-8")
        csv_path = self.root / "samples.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=self.csv_rows[0].keys())
            writer.writeheader()
            writer.writerows(self.csv_rows if csv_rows is None else csv_rows)
        return summarize(raw, self.manifest, self.configuration, csv_path)

    def test_valid_complete_and_absent_sites(self):
        result = self.run_summary()
        self.assertEqual(24, len(result["groups"]))
        self.assertEqual(6, result["validation"]["record_completeness"]["expected_complete_diagnostic_frames"])

    def test_empty(self):
        with self.assertRaisesRegex(ValueError, "Missing required calibration"):
            self.run_summary([])

    def test_truncated_json(self):
        with self.assertRaises(json.JSONDecodeError):
            self.run_summary(self.rows[:-1], suffix='{"type":')

    def test_missing_phase(self):
        with self.assertRaisesRegex(ValueError, "all 12 phase"):
            self.run_summary(self.rows[:-1])

    def test_duplicate_phase(self):
        with self.assertRaisesRegex(ValueError, "Duplicate diagnostic"):
            self.run_summary(self.rows+[self.rows[-1]])

    def test_missing_calibration(self):
        with self.assertRaisesRegex(ValueError, "Missing required calibration"):
            self.run_summary(self.rows[1:])

    def test_duplicate_calibration(self):
        with self.assertRaisesRegex(ValueError, "duplicate.*calibration"):
            self.run_summary(self.rows+[self.rows[0]])

    def test_missing_warmup_and_teardown(self):
        for kind in ("warmup", "teardown"):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "Missing warmup, measured, or teardown"):
                self.run_summary([row for row in self.rows if row.get("kind") != kind])

    def test_missing_or_duplicate_csv(self):
        with self.assertRaisesRegex(ValueError, "every requested measured frame"):
            self.run_summary(csv_rows=self.csv_rows[:1])
        with self.assertRaisesRegex(ValueError, "Duplicate CSV"):
            self.run_summary(csv_rows=self.csv_rows+[self.csv_rows[0]])

    def test_wrong_trial_or_order(self):
        for field, value in (("trial", 1), ("order", 1)):
            rows = copy.deepcopy(self.rows)
            rows[2][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.run_summary(rows)

    def test_missing_site_counters(self):
        rows = copy.deepcopy(self.rows)
        rows[2]["allocations"] = 1
        with self.assertRaisesRegex(ValueError, "Phase/site allocation records"):
            self.run_summary(rows)

    def test_csv_diagnostic_mismatch(self):
        csv_rows = copy.deepcopy(self.csv_rows)
        csv_rows[0]["allocated_bytes"] = 1
        with self.assertRaisesRegex(ValueError, "do not match CSV"):
            self.run_summary(csv_rows=csv_rows)


if __name__ == "__main__":
    unittest.main()
