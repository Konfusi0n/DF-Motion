#!/usr/bin/env python3
"""Generate, compile with native MSVC, and summarize interleaved offline trials."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

from generate import BASELINE, generate


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def bounded(maximum):
    def convert(value):
        result = int(value)
        if not 1 <= result <= maximum:
            raise argparse.ArgumentTypeError(f"Expected 1..{maximum}")
        return result
    return convert


def distribution(values):
    ordered = sorted(values)
    return {"count": len(values), "median": statistics.median(ordered),
            "p95": ordered[math.ceil(len(ordered) * .95) - 1],
            "p99": ordered[math.ceil(len(ordered) * .99) - 1],
            "worst": ordered[-1], "minimum": ordered[0]}


def summarize(raw_path, allocation_counts=False, attribution=False):
    with raw_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("Benchmark emitted no samples")
    groups = {}
    for row in rows:
        groups.setdefault((row["engine"], row["workload"], int(row["viewports"])), []).append(row)
    summaries = []
    for (engine, workload, viewports), samples in groups.items():
        entry = {"engine": engine, "workload": workload, "viewports": viewports,
                 "frame_samples": len(samples), "timing_units": "microseconds for all viewports in one fixture frame",
                 "allocation_counts_available": allocation_counts}
        for name in ("sync_ns", "collector_ns", "coverage_ns", "cleanup_ns", "total_ns"):
            entry[name.removesuffix("_ns") + "_us"] = distribution([int(row[name]) / 1000 for row in samples])
        allocation_fields = ("allocations", "allocated_bytes", "sync_allocations", "sync_allocated_bytes",
                     "collector_allocations", "collector_allocated_bytes", "coverage_allocations", "coverage_allocated_bytes",
                     "cleanup_allocations", "cleanup_allocated_bytes", "retained_bytes", "peak_live_bytes")
        for name in (allocation_fields if allocation_counts else ()) + ("proxies", "moving_proxies", "mirrored_proxies", "texture_calls", "covered_tiles"):
            entry[name] = distribution([int(row[name]) for row in samples])
        trial_groups, batch_groups = {}, {}
        for row in samples:
            trial_groups.setdefault(int(row["trial"]), []).append(row)
            batch_groups.setdefault((int(row["trial"]), int(row["batch"])), []).append(row)
        entry["trials"] = [{"trial": trial, "order": int(items[0]["order"]),
                             "sync_us": distribution([int(row["sync_ns"]) / 1000 for row in items]),
                             "collector_us": distribution([int(row["collector_ns"]) / 1000 for row in items]),
                             "coverage_us": distribution([int(row["coverage_ns"]) / 1000 for row in items]),
                             "cleanup_us": distribution([int(row["cleanup_ns"]) / 1000 for row in items]),
                             "total_us": distribution([int(row["total_ns"]) / 1000 for row in items])}
                            for trial, items in sorted(trial_groups.items())]
        entry["batch_mean_total_us"] = distribution([
            statistics.mean(int(row["total_ns"]) / 1000 for row in items) for items in batch_groups.values()])
        summaries.append(entry)
    comparisons = []
    keyed = {(entry["engine"], entry["workload"], entry["viewports"]): entry for entry in summaries}
    for entry in summaries:
        if entry["engine"] != "baseline":
            continue
        candidate = keyed[("candidate", entry["workload"], entry["viewports"])]
        total_changes, sync_changes = [], []
        for before, after in zip(entry["trials"], candidate["trials"], strict=True):
            if before["trial"] != after["trial"]:
                raise ValueError("Unpaired trial IDs")
            total_changes.append(100 * (after["total_us"]["median"] / before["total_us"]["median"] - 1))
            sync_changes.append(100 * (after["sync_us"]["median"] / before["sync_us"]["median"] - 1))
        comparisons.append({"workload": entry["workload"], "viewports": entry["viewports"],
                            "paired_trial_total_median_change_percent": total_changes,
                            "paired_trial_sync_median_change_percent": sync_changes,
                            "total_change_percent_distribution": distribution(total_changes),
                            "sync_change_percent_distribution": distribution(sync_changes),
                            "retained_bytes_median_delta": candidate["retained_bytes"]["median"] - entry["retained_bytes"]["median"] if allocation_counts else None,
                            "allocations_per_frame_median_delta": candidate["allocations"]["median"] - entry["allocations"]["median"] if allocation_counts else None})
    return {"frame_sample_count": len(rows), "quantiles": "nearest rank; median averages middle pair",
            "allocation_counts_available": allocation_counts,
            "measurement_mode": "diagnostic_attribution" if attribution else "allocation_instrumented" if allocation_counts else "clean_timing",
            "negative_change_means": "candidate lower cost", "groups": summaries, "comparisons": comparisons}


def system_info():
    info = {"platform": platform.platform(), "machine": platform.machine(), "python": sys.version,
            "logical_cpus": os.cpu_count(), "processor": platform.processor(),
            "process_priority": "inherited; not modified", "affinity": "inherited; not modified",
            "power_plan": "not changed or controlled", "concurrent_activity": "not controlled by harness"}
    if os.name == "nt":
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            info["cpu_name"] = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    return info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", default=BASELINE)
    parser.add_argument("--candidate-commit", help="Exact immutable candidate commit; required for attribution")
    parser.add_argument("--msvc-root", type=Path, required=True,
                        help="MSVC version root containing bin/Hostx64/x64/cl.exe and include")
    parser.add_argument("--sdk-root", type=Path, default=Path(r"C:\Program Files (x86)\Windows Kits\10"))
    parser.add_argument("--sdk-version", default="10.0.22621.0")
    parser.add_argument("--trials", type=bounded(20), default=6)
    parser.add_argument("--warmup", type=bounded(1000), default=24)
    parser.add_argument("--batches", type=bounded(100), default=6)
    parser.add_argument("--batch-frames", type=bounded(1000), default=16)
    parser.add_argument("--workload", choices=("all", "idle", "paused", "small_moving", "dense_200", "frequent_changes", "pan_context"), default="all")
    parser.add_argument("--viewports", choices=("all", "1", "9"), default="all")
    parser.add_argument("--build-only", action="store_true", help="Capture/build inputs without executing timings")
    parser.add_argument("--allocation-counts", action="store_true",
                        help="Separate instrumented allocation run; primary timing runs omit replacement allocation operators entirely")
    parser.add_argument("--attribution", action="store_true", help="Source-tagged diagnostic phases and allocation sites; separate from clean timings")
    args = parser.parse_args()
    if args.attribution and not args.candidate_commit:
        parser.error("Attribution requires --candidate-commit to freeze its exact production inputs")
    if args.attribution:
        args.allocation_counts = True
    output, msvc, sdk = args.output.resolve(), args.msvc_root.resolve(), args.sdk_root.resolve()
    source = generate(args.repo, output, args.baseline, args.candidate_commit, args.attribution)
    compiler = msvc / "bin" / "Hostx64" / "x64" / "cl.exe"
    if not compiler.is_file():
        parser.error("MSVC compiler does not exist at the supplied version root")
    environment = os.environ.copy()
    removed_option_variables = []
    for key in list(environment):
        if key.upper() in ("CL", "_CL_", "LINK", "_LINK_"):
            removed_option_variables.append(key)
            del environment[key]
    environment["INCLUDE"] = os.pathsep.join(str(path) for path in [msvc / "include"] + [
        sdk / "Include" / args.sdk_version / folder for folder in ("ucrt", "shared", "um", "winrt")])
    environment["LIB"] = os.pathsep.join(str(path) for path in [msvc / "lib" / "x64"] + [
        sdk / "Lib" / args.sdk_version / folder / "x64" for folder in ("ucrt", "um")])
    environment["PATH"] = os.pathsep.join([str(compiler.parent), str(sdk / "bin" / args.sdk_version / "x64"), environment.get("PATH", "")])
    executable = output / "presentation-performance.exe"
    command = [str(compiler), "/Bv", "/std:c++17", "/O2", "/MD", "/EHsc", "/UNDEBUG", "/W4",
               "/DDF_MOTION_ALLOCATION_COUNTS=" + str(int(args.allocation_counts)),
               "/DDF_MOTION_ATTRIBUTION=" + str(int(args.attribution)),
               str(output / "presentation-performance.cpp"), "/Fe:" + str(executable),
               "/Fo:" + str(output / "presentation-performance.obj"), "/link", "/MACHINE:X64"]
    receipt = {"started_at": utc(), "system": system_info(), "source": source,
               "compiler": str(compiler), "compiler_sha256": digest(compiler), "compiler_arguments": command,
               "sdk_version": args.sdk_version, "runner_sha256": digest(__file__),
               "inherited_tool_option_variables_removed": removed_option_variables,
               "measurement_mode": "diagnostic_attribution" if args.attribution else "allocation_instrumented" if args.allocation_counts else "clean_timing",
               "replacement_allocation_operators_compiled": args.allocation_counts,
               "configuration": {"trials_per_variant": args.trials, "warmup_frames_per_trial": args.warmup,
                                 "batches_per_trial": args.batches, "frames_per_batch": args.batch_frames,
                                 "viewport_shape": [100, 60], "viewport_counts": [1, 9] if args.viewports == "all" else [int(args.viewports)],
                                 "workload_filter": args.workload, "viewport_filter": args.viewports,
                                 "presentation_time_step_ms": 4, "paused_time_step_ms": 0,
                                 "small_entities": 10, "dense_entities_per_viewport": 200,
                                 "invalidation_entities_per_viewport": 50},
               "allocation_scope": "Production synchronization, collection, coverage, and destruction only; requested C++ new bytes, excluding allocator metadata/RSS; accounting hooks add common measurement overhead" if args.allocation_counts else "Unavailable in clean timing mode; raw CSV allocation columns are zero placeholders, not evidence of zero allocations",
               "timing_scope": "Sum of four separately timed production phases, excluding fixture updates, checksums, CSV output, warmup, and sample storage; includes allocation-free texture-call digest; instrumented mode also includes allocation accounting and is not primary performance evidence",
               "limitations": "Synthetic CPU fixture with all nine layers; no SDL rendering/GPU/real cache; 9 viewports each contain a full independent entity set; no real fortress FPS or visual acceptance"}
    receipt_path = output / "run-receipt.json"
    def save():
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    save()
    with (output / "compile.log").open("wb") as log:
        result = subprocess.run(command, cwd=output, env=environment, stdout=log, stderr=subprocess.STDOUT)
    receipt["compile_exit_code"] = result.returncode
    if result.returncode:
        save()
        raise SystemExit(f"MSVC build failed; inspect {output / 'compile.log'}")
    receipt["executable_sha256"] = digest(executable)
    if args.build_only:
        receipt["status"] = "build_only_not_measured"
        save()
        print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path)}, indent=2))
        return
    run_command = [str(executable), str(args.trials), str(args.warmup), str(args.batches), str(args.batch_frames), args.workload, args.viewports]
    receipt["run_arguments"] = run_command
    start = time.monotonic()
    diagnostic_path = output / ("raw-attribution.jsonl" if args.attribution else "run.stderr.log")
    with (output / "raw-samples.csv").open("wb") as raw, diagnostic_path.open("wb") as errors:
        result = subprocess.run(run_command, cwd=output, stdout=raw, stderr=errors)
    receipt["run_exit_code"] = result.returncode
    receipt["elapsed_seconds"] = time.monotonic() - start
    receipt["completed_at"] = utc()
    receipt["raw_samples_sha256"] = digest(output / "raw-samples.csv")
    if result.returncode:
        receipt["status"] = "failed_no_performance_conclusion"
        save()
        raise SystemExit(f"Benchmark failed; inspect {diagnostic_path}")
    summary = summarize(output / "raw-samples.csv", args.allocation_counts, args.attribution)
    expected_samples = args.trials * args.batches * args.batch_frames * 2 * (6 if args.workload == "all" else 1) * (2 if args.viewports == "all" else 1)
    if summary["frame_sample_count"] != expected_samples:
        receipt["status"] = "failed_incomplete_samples"
        save()
        raise SystemExit("Benchmark did not emit the exact requested sample count")
    receipt["expected_frame_samples"] = expected_samples
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    receipt["summary_sha256"] = digest(output / "summary.json")
    if args.attribution:
        import attribution_summary
        try:
            details = attribution_summary.summarize(diagnostic_path, output / "insertion-manifest.json",
                                                    receipt["configuration"], output / "raw-samples.csv")
        except Exception as error:
            receipt["status"] = "failed_attribution_validation"
            receipt["attribution_error"] = str(error)
            save()
            raise
        (output / "attribution-summary.json").write_text(json.dumps(details, indent=2) + "\n", encoding="utf-8")
        receipt["attribution_summary_sha256"] = digest(output / "attribution-summary.json")
        receipt["raw_attribution_sha256"] = digest(diagnostic_path)
        receipt["attribution_summarizer_sha256"] = digest(Path(__file__).with_name("attribution_summary.py"))
    receipt["status"] = "completed_offline_measurement"
    receipt["output_digests_equal_every_paired_frame"] = True
    save()
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path),
                      "sample_count": summary["frame_sample_count"], "comparisons": summary["comparisons"]}, indent=2))


if __name__ == "__main__":
    main()
