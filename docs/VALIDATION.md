# DF Motion validation record

This document records what the consolidated candidate proves and where evidence still stops. It is intentionally specific so a fast CPU fixture is never mistaken for a live Dwarf Fortress frame-rate claim.

## Candidate identity

- Final source: `041de61c201b058cc8c1880e33384aa261d5796c`
- Frozen indexed baseline: `5a4c448440d732097ace2a0cb415d8762c0a0d30`
- Target runtime: Dwarf Fortress 0.53.16 / DFHack 53.16-r1.1
- Windows candidate: `smooth-movement.plug.dll`
- Windows SHA-256: `43850CC6C4557BAB82E05C1471181B7D4B1F92F206F78ACBF315865864A534EE`
- PDB SHA-256: `01BD742430A369AA0F7F103BA2DB9A00D2AE0AE0760746A591EDB157509DE4D5`
- Display setup readback: 2560×1440 windowed, simulation cap 120, graphics cap 240

The candidate DLL was installed and loaded in a controlled test save. That confirms identity and lifecycle for this run. It does not confirm a matched control/candidate visual result.

The PDB is not shipped in the release folder; its hash is retained here only as build provenance. CI's Linux and Windows outputs are run artifacts, while the committed release folder intentionally carries the selected Windows candidate.

## Retained source changes

| Commit | Proof-relevant change |
| --- | --- |
| `4c954b9de0380e272c8482aea93ca6a2a4d93859` | Restore incoming SDL clip, color, and viewport origin |
| `38a2d431d89737096667e96b5ce0c96df05e6d5b` | Capture interpolation policy per movement |
| `9834475a8ccdb0239fabb0db6ade327e9402a93f` | Separate clean timing from diagnostic attribution |
| `041de61c201b058cc8c1880e33384aa261d5796c` | Reserve proxy capacity after candidate deduplication |

Earlier high-refresh and identity-continuity history remains in `d87d03e`, `381fb84`, and `48020d0`. Upstream PR #22 and PR #24 are credited in the README.

## Behavioral and native proof

- Fresh manager and collector suites pass under MSVC and Zig with assertions enabled.
- Fixed-mode oracle runs report 17,733,654 lookups, 17,217 collectors, 18,001 index checks, and 59,771 proxies, including 57,593 moving and 2,178 resting mirrors.
- SDL offscreen proof covers 55 cases, 128 state checks, and 294,912 pixel comparisons at scales 1, 1.25, and 2.
- The production-tail integration seam covers 36 cases, 189 callbacks, and 36 fills.
- Geometry proof covers tile widths 16, 24, 32, 40, 48, 56, and 64 pixels, with 30,912 endpoint-axis checks, 37,317 sprite draws, 6,720 cargo draws, 12,096 fragment associations, 336 chains, and 10,815 erase rectangles.
- Policy proof covers both switch directions, non-midpoint progress, synchronization boundaries, learned duration, stale predecessors, rollover, mixed-policy ambiguity, and indexed/fallback companion paths.
- Negative controls for renderer, geometry, and policy compile and fail as expected under both compilers.
- The native DFHack 53.16-r1.1 build exits successfully with release dynamic CRT linkage. Static inspection establishes x64, ABI 2, 11 exports, 27 resolved DFHack imports, unchanged release-runtime imports, and eight required dynamic SDL symbols.

Static inspection is not Windows loader acceptance. The controlled candidate runtime readback supplies the separate lifecycle check.

## Offline performance

Final comparison: `5a4c448` → `041de61`. Six clean trials use 24 warmup frames and 96 measured frames per fixture, engine, and trial. The trace holds the real default smoothstep policy fixed. The fixture measures complete managers and collection paths; SDL draws and GPU work are outside this timing scope.

Synthetic CPU timing, microseconds per complete fixture frame:

| Fixture | Median baseline → final | p95 baseline → final | p99 baseline → final | Maximum baseline → final |
| --- | ---: | ---: | ---: | ---: |
| Dense 200, one viewport | 1,339.75 → 1,006.50 | 1,642.5 → 1,243.6 | 1,787.3 → 1,363.0 | 2,060.5 → 1,433.3 |
| Frequent changes, one | 1,507.60 → 1,178.80 | 1,721.8 → 1,313.1 | 1,874.4 → 1,386.6 | 2,097.8 → 1,524.2 |
| Dense 200, nine | 12,298.80 → 9,392.10 | 14,305.2 → 11,554.4 | 14,876.1 → 12,101.2 | 20,854.7 → 15,666.3 |
| Frequent changes, nine | 13,772.35 → 10,732.75 | 15,076.7 → 11,827.9 | 16,206.5 → 12,173.6 | 25,466.6 → 15,664.7 |
| Idle, one | 53.80 → 53.80 | 63.7 → 61.7 | 107.2 → 91.9 | 146.9 → 140.2 |
| Paused, nine | 490.15 → 491.55 | 580.7 → 587.3 | 643.0 → 656.6 | 769.6 → 795.9 |

There are 13,824 clean measured rows and 4,608 separate allocation rows. All 36 paired busy medians improve across the small, dense, and frequent fixtures at one and nine viewports. Dense-nine pooled median improves 23.63%; frequent-nine improves 22.07%.

Busy nine-viewport peak requested memory changes from 8,701,790 to 8,832,038 bytes, an increase of 130,248 bytes. Retained requested bytes are unchanged. The reserve is a capacity hint; it does not change containers, ordering, matching, or entity state.

These timings are synthetic CPU work. They do not establish game FPS, frame-pacing intervals, display presents, input latency, GPU time, or player-perceived smoothness.

## Rejected experiments

- Combined exact snapshots and scratch reuse passed functional tests, but the predeclared frequent-nine repeat gate remained ambiguous. Total medians worsened in 7/12 trials and p95 in 8/12; retained requested storage also grew.
- Scratch reuse alone passed behavioral checks, but frequent-nine medians worsened in 4/12 and p95 in 5/12, with paired median changes ranging from −13.905% to +7.072%. Persistent storage was not retained.
- A geometry rewrite passed reachable normal-zoom seams but did not demonstrate a production defect. Existing geometry remains the authority.
- Larger container changes, arbitrary capacity multipliers, new easing, spring cameras, animated zoom, and UI motion were not justified by the measured proof boundary.

The rejected results remain in the preserved evidence bundle. A bounded test subset that survives a mutation is not relabeled as detection.

## Live proof still required

The next live run should use a saved temporary copy and alternate control/candidate runs:

1. Close the game before every swap.
2. Verify the exact control, candidate, and installed DLL hashes.
3. Use 2560×1440 windowed with identical simulation/graphics settings, toggles, zoom, camera, and starting scene.
4. Warm up for 20 seconds, then capture 60 seconds per run.
5. Record present intervals, median/p95/p99/max interval, interval buckets around 8.333/16.667/33.333 ms, and actual simulation throughput.
6. Inspect landings, chains, cargo, multi-tile alignment, mirroring, camera motion, pause, mode changes, clipping, resize, and zoom.
7. Treat unavailable display timing as missing data, never as presumed dropped frames.
8. Restore the supported winning build after the comparison.

This protocol is the boundary between offline engineering confidence and end-user wow-factor evidence.
