#!/usr/bin/env python3
"""Summarize diagnostic records without treating them as clean performance costs."""
from collections import defaultdict
import csv
import json
import math
import statistics

WORKLOADS = ("idle", "paused", "small_moving", "dense_200", "frequent_changes", "pan_context")
PHASES = ("synchronization", "candidate_generation", "sort_unique", "moving_proxy", "center_anchor",
          "resting_mirrored", "texture_adapter", "coverage", "returned_destruction", "collector_other",
          "teardown", "allocator_call")


class RecordContract:
    """Bind every diagnostic record to the requested fixture and CSV frame."""
    def __init__(self, configuration, csv_path):
        self.trials = configuration["trials_per_variant"]
        self.warmup = configuration["warmup_frames_per_trial"]
        self.batches = configuration["batches_per_trial"]
        self.batch_frames = configuration["frames_per_batch"]
        for value in (self.trials, self.warmup, self.batches, self.batch_frames):
            if type(value) is not int or value < 1:
                raise ValueError("Expected configuration needs positive integer frame/trial counts")
        self.measured = self.batches * self.batch_frames
        self.viewports = configuration["viewport_counts"]
        if not self.viewports or len(set(self.viewports)) != len(self.viewports) or any(type(v) is not int or v not in (1, 9) for v in self.viewports):
            raise ValueError("Unexpected or duplicate viewport configuration")
        workload = configuration["workload_filter"]
        if workload != "all" and workload not in WORKLOADS:
            raise ValueError("Unknown workload configuration")
        self.workloads = WORKLOADS if workload == "all" else (workload,)
        self.expected_trials = self.trials * len(self.viewports) * len(self.workloads) * 2
        self.expected_frames = self.expected_trials * (self.warmup + self.measured + 1)
        self.csv_rows, self.frames, self.seen, self.calibrations = {}, {}, set(), set()
        with csv_path.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                for field in ("viewports", "trial", "order", "frame", "batch"):
                    row[field] = int(row[field])
                row["kind"] = "frame"
                key = self.key(row)
                if key in self.csv_rows:
                    raise ValueError("Duplicate CSV frame identity")
                if row["batch"] != row["frame"] // self.batch_frames:
                    raise ValueError("CSV batch does not match requested frame grouping")
                self.csv_rows[key] = row
        if len(self.csv_rows) != self.expected_trials * self.measured:
            raise ValueError("CSV does not contain every requested measured frame")

    def key(self, row):
        engine, workload = row["engine"], row["workload"]
        viewports, trial, order, frame = (row[field] for field in ("viewports", "trial", "order", "frame"))
        if any(type(value) is not int for value in (viewports, trial, order, frame)):
            raise ValueError("Diagnostic frame identity must use integer indices")
        if engine not in ("baseline", "candidate") or workload not in self.workloads or viewports not in self.viewports or not 0 <= trial < self.trials:
            raise ValueError("Record identity is outside the requested configuration")
        baseline_order = (trial + WORKLOADS.index(workload) + (viewports == 9)) & 1
        if order != (baseline_order if engine == "baseline" else 1-baseline_order):
            raise ValueError("Record order does not match interleaved AB/BA configuration")
        kind = row["kind"]
        if not ((kind == "warmup" and -self.warmup <= frame < 0) or
                (kind == "frame" and 0 <= frame < self.measured) or
                (kind == "teardown" and frame == self.measured)):
            raise ValueError("Record frame/kind is outside the requested configuration")
        return engine, workload, viewports, trial, order, kind, frame

    def accept(self, row, site_names):
        kind = row["type"]
        if kind == "calibration":
            name = row["name"]
            if name not in ("clock_pair", "empty_scope") or name in self.calibrations or row["samples"] != 2048:
                raise ValueError("Unknown, duplicate, or incomplete calibration")
            values = [row[field] for field in ("median_ns", "p95_ns", "p99_ns", "worst_ns")]
            if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 for value in values) or values != sorted(values):
                raise ValueError("Invalid calibration quantiles")
            self.calibrations.add(name)
            return
        if kind not in ("phase", "site"):
            raise ValueError("Unknown diagnostic record type")
        key, identifier = self.key(row), row["id"]
        if type(identifier) is not int or (kind == "phase" and not 0 <= identifier < len(PHASES)) or (kind == "site" and identifier not in site_names):
            raise ValueError("Unknown diagnostic phase/site ID")
        identity = key + (kind, identifier)
        if identity in self.seen:
            raise ValueError("Duplicate diagnostic phase/site record")
        self.seen.add(identity)
        frame = self.frames.setdefault(key, {"phases": set(), "phase": [0]*5, "site": [0]*5})
        if kind == "phase":
            if row["phase"] != PHASES[identifier]:
                raise ValueError("Phase name does not match its ID")
            frame["phases"].add(identifier)
        for i, field in enumerate(("allocations", "requested_bytes", "frees", "freed_bytes", "live_bytes")):
            value = row[field]
            if type(value) is not int or value < 0:
                raise ValueError("Invalid diagnostic allocation counter")
            frame[kind][i] += value

    def finish(self):
        if self.calibrations != {"clock_pair", "empty_scope"}:
            raise ValueError("Missing required calibration records")
        if len(self.frames) != self.expected_frames:
            raise ValueError("Missing warmup, measured, or teardown diagnostic frames")
        for key, frame in self.frames.items():
            if frame["phases"] != set(range(len(PHASES))):
                raise ValueError("Every diagnostic frame requires all 12 phase records exactly once")
            if frame["phase"] != frame["site"]:
                raise ValueError("Phase/site allocation records do not reconcile")
            if key[5] == "frame":
                csv_row = self.csv_rows[key]
                if [int(csv_row[field]) for field in ("allocations", "allocated_bytes", "retained_bytes")] != [frame["phase"][i] for i in (0, 1, 4)]:
                    raise ValueError("Diagnostic allocations/bytes/retention do not match CSV frame")
        return {"expected_complete_diagnostic_frames": self.expected_frames,
                "measured_frame_keys_match_csv": len(self.csv_rows), "all_12_phases_once_per_frame": True,
                "warmup_and_teardown_complete": True, "exact_calibration_pair": True,
                "duplicate_records_rejected": True, "frame_phase_site_csv_counters_reconcile": True}


def distribution(values):
    values = sorted(values)
    return {"samples": len(values), "median": statistics.median(values),
            "p95": values[math.ceil(len(values)*.95)-1],
            "p99": values[math.ceil(len(values)*.99)-1], "max": values[-1]}


def weighted_median(histogram):
    count = sum(histogram.values())
    if not count:
        return None
    left, right, total, found = (count-1)//2, count//2, 0, []
    for size, amount in sorted(histogram.items()):
        if total <= left < total+amount:
            found.append(size)
        if total <= right < total+amount:
            found.append(size)
        total += amount
    return sum(found)/len(found)


def summarize(path, manifest_path, configuration, csv_path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    names = {entry["id"]: entry for entry in manifest["sites"]}
    if len(names) != len(manifest["sites"]):
        raise ValueError("Duplicate source-site IDs in manifest")
    contract = RecordContract(configuration, csv_path)
    groups, lifecycle, calibration, frames = defaultdict(list), defaultdict(list), [], defaultdict(set)
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            contract.accept(row, names)
            if row["type"] == "calibration":
                calibration.append(row)
                continue
            fixture = (row["engine"], row["workload"], row["viewports"])
            key = fixture + (row["type"], row["id"])
            lifecycle[key].append(row)
            if row["kind"] == "frame":
                groups[key].append(row)
                frames[fixture].add((row["trial"], row["frame"]))
    completeness = contract.finish()
    result = []
    fields = ("inclusive_ns", "exclusive_ns", "calls", "allocations", "requested_bytes", "backing_bytes",
              "frees", "freed_bytes", "malloc_ns", "free_ns", "live_bytes", "peak_live_bytes")
    for key, rows in sorted(groups.items()):
        engine, workload, viewports, kind, identifier = key
        frame_count = len(frames[key[:3]])
        entry = {"engine": engine, "workload": workload, "viewports": viewports, "kind": kind, "id": identifier,
                 "name": rows[0]["phase"] if kind == "phase" else names[identifier]["name"], "frame_samples": frame_count}
        entry["measurement_availability"] = {
            "scope_cpu_time": "instrumented" if kind == "phase" else "not_collected",
            "scope_invocations": "collected" if kind == "phase" else "not_collected",
            "raw_allocator_windows": "instrumented_malloc_free_only",
        }
        for field in fields:
            if kind == "site" and field in ("inclusive_ns", "exclusive_ns", "calls"):
                entry[field] = None
                continue
            values = [row[field] for row in rows] + [0]*(frame_count-len(rows))
            entry[field] = distribution(values)
        sizes = defaultdict(int)
        for row in rows:
            for size, count in row["size_histogram"]:
                sizes[size] += count
        entry["allocation_size_histogram"] = sorted(sizes.items())
        entry["median_allocation_size"] = weighted_median(sizes)
        life = lifecycle[key]
        count = sum(row["lifetimes"] for row in life)
        entry["whole_trial_lifecycle_including_warmup_teardown"] = {
            "allocations": sum(row["allocations"] for row in life),
            "frees": sum(row["frees"] for row in life), "lifetimes": count,
            "same_frame_frees": sum(row["same_frame_frees"] for row in life),
            "lifetime_frames_max": max(row["lifetime_frames_max"] for row in life),
            "instrumented_lifetime_ns_mean": sum(row["lifetime_ns_sum"] for row in life)/count if count else None,
            "instrumented_lifetime_ns_min": min((row["lifetime_ns_min"] for row in life if row["lifetimes"]), default=None),
            "instrumented_lifetime_ns_max": max(row["lifetime_ns_max"] for row in life),
            "allocation_phase_counts": [sum(row["allocation_phase_counts"][i] for row in life) for i in range(12)],
            "free_phase_counts": [sum(row["free_phase_counts"][i] for row in life) for i in range(12)],
        }
        if kind == "site":
            entry["source_locations"] = names[identifier].get("locations", [])
        result.append(entry)
    for key, rows in lifecycle.items():
        if key[3] == "site":
            if sum(row["allocations"] for row in rows) != sum(row["frees"] for row in rows):
                raise ValueError(f"Allocation ownership does not balance across complete trials: {key}")
        for row in rows:
            if row["kind"] == "teardown" and row["live_bytes"]:
                raise ValueError("Tracked bytes remain at teardown")
    return {"mode": "diagnostic_attribution_not_clean_timing", "calibration": calibration,
            "source_site_registry": manifest["sites"], "groups": result,
            "validation": {"site_allocation_frees_balance_including_warmup_teardown": True,
                           "teardown_live_bytes_zero": True,
                           "record_completeness": completeness,
                           "native_probe_checks": "Scopes bounded/closed, site+phase counts/bytes reconcile, no unattributed allocation; failures terminate executable"},
            "interpretation": "Inclusive times contain children; exclusive phase costs subtract timed child scopes and raw allocator calls. Scope/metadata/histogram overhead remains and is not subtracted. Allocator timings use larger backing requests with diagnostic headers and clock overhead; they do not estimate a counterfactual percentage of clean frame time. Lifetimes include diagnostic and output overhead. Texture timings are fixture-adapter only."}
