# Offline presentation cost and allocation comparison

This is a bounded CPU microbenchmark, not a game-FPS benchmark. It uses both
complete production managers and the exact production proxy collector and
coverage collector. `generate.py` reuses the equivalence harness's declaration
extractor and never rewrites the extracted production bodies. The default
reference is frozen commit `5a4c448440d732097ace2a0cb415d8762c0a0d30`;
`--baseline` accepts another exact 40-character commit for an explicitly separate
stage comparison. The candidate is a byte snapshot of the selected working tree.

The native Windows runner uses Python's standard library and MSVC. Every process
uses an argument list, without a shell or network operation. Build environment
changes apply only to the compiler subprocess; inherited `CL`, `_CL_`, `LINK`, and `_LINK_` option variables are
removed before compilation. Output filenames are fixed within
a newly created evidence directory, reserved atomically by the generator. Both
entry points reject any existing output directory, including an empty one.
It does not install a plugin, start Dwarf Fortress, change process affinity or
priority, or modify system settings.

Example from the repository root (replace the absolute tool/evidence paths):

```text
python tests/performance/run.py --repo . --output C:/evidence/stage1-performance --msvc-root C:/tools/msvc/VC/Tools/MSVC/14.44.35207
```

`--build-only` captures and compiles the same source without executing timings.
The default is clean timing: replacement allocation operators are excluded at
compile time, so the production code uses the compiler's ordinary allocator.
Run separately with `--allocation-counts` and a different new output directory
to collect allocation evidence. This second run can use fewer trials, but keep
the fixture/frame settings and exact source hashes the same. Do not mix its
timing distributions with the clean timing result. Clean-mode raw CSV allocation
columns are zero placeholders and are omitted from the summary, not reported as
zero allocations.
Other bounded options are `--trials 6`, `--warmup 24`, `--batches 6`, and
`--batch-frames 16`. A smoke run with fewer samples only verifies the harness;
use repeated trials for a performance decision. Run when other compilation and
test work has finished. Background OS activity remains uncontrolled and is a
reason to examine paired-trial consistency and tails, not just one median.

By default every workload runs at both viewport counts. Validated optional
filters select one workload and/or viewport count: for example
`--workload frequent_changes --viewports 9 --trials 12` isolates the busiest
fixture. `all` retains the default selection. Receipts record both filters, and
the native executable validates them independently. Keep a targeted repeat's
samples separate from previous runs, particularly when the driver hash changed.

Each trial resets the manager and constructs fresh 100×60 viewport buffers. The
six workloads each run with one and nine viewports:

| Workload | Fixture |
| --- | --- |
| Idle | Empty, unchanged buffers with advancing presentation time |
| Paused | 200 stationary creatures, unchanged buffers and repeated timestamp |
| Small moving | 10 creatures stepping every six presentation frames |
| Dense 200 | 200 creatures per viewport stepping every six frames |
| Frequent changes | 200 creatures per viewport stepping every frame |
| Pan/context | 50 creatures, pending and landed pan buffers, periodic context changes |

Creatures carry item/designation layers and multiple body fragments. Every tenth
creature has a vehicle-layer fixture whose texture also changes. This is a
synthetic load: nine viewports means nine independent full entity sets, not a
claim about how many entities real DF lower viewports contain. Presentation time
advances 4 ms except while paused. The workload does not change interpolation
mode mid-flight; that intentional behavioral change is validated by dedicated
regression tests, not a performance timing comparison.

Trials alternate AB/BA by trial/workload/viewport count. Warmup frames are
discarded. Raw CSV preserves each measured frame, phase times, trial/order/batch
IDs, operation counts, output checksum, per-phase and total allocation count/bytes, retained bytes,
and peak live requested bytes. `summary.json` provides median, nearest-rank p95
and p99, worst, minimum, per-trial distributions, batch means, and paired-trial
percentage changes. Negative changes mean lower candidate cost. Total time is
for all viewports in one fixture frame, not time per viewport.

Four production phases are timed separately: manager synchronization, proxy
collection, coverage collection, and destruction of returned containers. The
total is their sum. Fixture buffer updates, output checksums, CSV I/O, and sample
storage are outside those timers. A deterministic, allocation-free texture
adapter records lookup count and order digest inside collector timing. Complete
proxy and coverage outputs contribute to a digest outside timing and must match
between every corresponding baseline/candidate frame. Digests and counts prevent
dead-code elimination and catch accidental fixture divergence; the much broader
equivalence harness remains the behavioral oracle.

With `--allocation-counts`, the executable overrides C++ allocation operators solely to measure allocations
made within the four production phases. These accounting hooks are test-only;
the plugin does not gain a custom allocator. Fixture allocations are excluded.
Allocations are followed through deallocation even outside the recording scope.
`retained_bytes` is measured after proxy/coverage destruction, so it represents
manager-owned allocations; `peak_live_bytes` also includes temporary production
containers. Warmup allocations that remain live are included in retained memory.
Engine teardown must return tracked live bytes to zero. Requested bytes exclude
allocator metadata, fragmentation, non-`new` allocations, and process RSS. The
accounting headers/counters add common measurement overhead. Use the separate
clean-mode result for the retention decision and the instrumented run to explain
allocation and memory costs.

The receipt binds the full source snapshots, baseline commit, candidate HEAD and
production dirty-file status, extractor/generator/template/runner hashes,
generated translation unit, compiler and executable hashes, MSVC command,
Windows SDK version, CPU/system identity, fixture parameters, raw CSV, and final
summary. The compiler's complete version report is retained in `compile.log`.

The adapters omit SDL drawing, native DF objects/ABI, real texture-cache work,
GPU time, game input, and fortress simulation. A retained optimization still
needs independent correctness, native plugin, and eventual live-game proof.
