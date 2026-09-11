# Collector and coverage attribution

Use this diagnostic to locate work before choosing an optimization. Allocation
count is not proof that allocation is the dominant cost. The retained production
candidate and the previously rejected snapshot optimization are separate inputs;
this pass pins `4c954b9de0380e272c8482aea93ca6a2a4d93859` and does not restore
snapshot caching or change production containers.

Three modes remain distinct:

| Mode | Purpose | Perturbation |
| --- | --- | --- |
| Default clean timing | Repeated complete CPU-phase comparison | Ordinary allocation operators; no diagnostic markers or probe header |
| `--allocation-counts` | Coarse phase allocation counts and retained bytes | Test allocation headers/counters |
| `--attribution` | Detailed phase and source-site diagnosis | Scope clocks, allocation headers, size histograms, lifetime accounting |

Attribution requires an exact `--candidate-commit`. For example, from the repo:

```text
python tests/performance/run.py --repo . --output C:/evidence/attribution-diagnostic --msvc-root C:/tools/msvc/VC/Tools/MSVC/14.44.35207 --candidate-commit 4c954b9de0380e272c8482aea93ca6a2a4d93859 --attribution --trials 2 --warmup 24 --batches 6 --batch-frames 16
```

Use another new output directory with the same candidate commit and fixture
parameters, omit `--attribution`, and increase to six trials for the clean
control. Run clean measurements only after other compiler/test activity stops.
Do not pool clean and diagnostic timing distributions or different source inputs.

`instrument.py` operates on copied collector/coverage declarations. It inserts
scope and site markers without replacing production characters. Every expected
anchor must match the expected number of occurrences. The insertion manifest
records original expression, line, hash, namespace, offsets, and inserted text.
Removing those exact insertions must reconstruct the pristine declaration byte
for byte. Raw production snapshots remain untouched in the evidence directory;
instrumented declarations are saved separately. Diagnostic receipts explicitly
mark their generated production bodies as modified by instrumentation.

Markers split synchronization, candidate generation/conversion, sort/unique,
moving-proxy construction, center-anchor bookkeeping, resting/mirrored proxies,
texture-adapter lookup, coverage, returned-container destruction, residual
collector work, and teardown. Allocation sites distinguish proxy construction,
proxy-vector growth, per-proxy coverage nodes, mirrored coverage nodes, the
resting drawn set, and aggregate coverage containers. Synchronization remains an
explicit aggregate site; this is not a complete manager allocation call graph.
Return/move/wrapper allocations have named residual sites instead of being
silently assigned to another expression.

`attribution_probe.h` exists only in diagnostic builds. Fixed-capacity scopes and
site/size tables allocate no probe storage while production calls are measured.
Overflow, unclosed scopes, unattributed allocation, mismatched site/phase/global
totals, or surviving tracked memory fail validation. Returned objects keep their
allocation-site ownership in the diagnostic header; frees report both that
ownership and their destruction phase. Size histograms provide exact allocation
size medians for the observed C++ `new` requests. The backing allocation also
includes diagnostic metadata and alignment padding and is reported separately.

`raw-attribution.jsonl` contains calibration, every phase, and active site records
for warmup, measured frames, and teardown. It is emitted outside production
timing and allocation scopes. `attribution-summary.json` reports per-frame
median, p95, p99, maximum, counts, requested/backing bytes, retained/peak bytes,
weighted allocation-size median, and complete-trial lifetime summaries. It
includes allocation/free phase-count arrays in the documented phase order below.
Sites absent from a measured frame receive zero when calculating distributions;
warmup and teardown are excluded from frame timing quantiles but retained for
allocation-lifetime balance.

Source-site records attribute allocation ownership and raw allocator windows;
they do not time the entire source statement. Their scope-time and invocation
fields are `null` with explicit `not_collected` availability. The allocator-call
phase records malloc/free child timing and calls; allocation counts and bytes
remain assigned to the owning phases so they are not counted twice.

The summarizer requires the requested configuration and companion CSV. It rejects
missing/duplicate CSV frame identities, incorrect AB/BA ordering, missing or
duplicate calibration, and any missing/duplicate phase record. Every requested
warmup, measured, and teardown frame must contain all 12 phases exactly once.
Source sites may be absent when inactive; per-frame phase/site totals must still
reconcile, and measured allocations/bytes/retention must match the CSV.

Phase-array order: synchronization, candidate_generation, sort_unique,
moving_proxy, center_anchor, resting_mirrored, texture_adapter, coverage,
returned_destruction, collector_other, teardown, allocator_call.

Inclusive phase time contains child work. Exclusive time subtracts the measured
child scope durations and raw allocator-call windows. Do not add inclusive child
and parent times. Probe bookkeeping, timer calls, histogram updates, and changed
code generation remain; exclusive time is not an unbiased native cost estimate.

The allocator subphase measures raw `malloc`/`free` windows used by diagnostic
replacement operators. Clock-pair and empty-scope distributions are recorded
before trials. Tiny allocator calls can be comparable to clock resolution or
measurement overhead, including zero-duration samples. Report raw calibration
and this limit; do not subtract a median overhead and call the result exact.
Diagnostic headers change backing request sizes and allocator behavior, so these
windows cannot establish the allocator's counterfactual percentage of a clean
frame. Instrumented lifetimes include probe and output overhead; frame lifetimes
and destruction-phase ownership are more directly interpretable.

The texture adapter still supplies fixed fixture textures and a lookup-order
digest. Its timing is explicitly adapter-only. Real DF tile-cache lookup, SDL
draws, GPU time, gameplay, and game FPS remain outside this executable.

Before using attribution, compare its entire fixture output against a pristine
clean executable using the same frozen inputs. Matching two instrumented
namespaces alone cannot exclude a shared marker-insertion mistake. Native MSVC
is authoritative for Windows STL allocation behavior. Zig validates output and
probe accounting too, but its library's allocation counts and timings need not
match MSVC. Any later scratch-only or container experiment needs its own isolated
source revision, oracle validation, and repeated clean timing decision.
