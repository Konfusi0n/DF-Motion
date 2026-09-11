# DF Motion roadmap

DF Motion is being developed as a presentation layer for Dwarf Fortress. The simulation remains the authority; this roadmap is about continuity, frame pacing, and visual confidence between authoritative updates.

## North star

At high refresh, the fortress should feel present rather than sampled. A unit should leave one tile and arrive at the next with a stable trajectory. A crowd should not collapse into zippering or duplicate sprites. A camera glide should settle without a hitch or renderer-state leak. Pause, teleport, death, disappearance, and mode changes should remain unambiguous.

## Shipped in the consolidated candidate

- Elapsed-time scroll watchdog with a monotonic clock and 32-bit rollover behavior.
- Active movement indexing by layer and tile while preserving exact multi-tile anchors and movement IDs.
- SDL clip, color, and viewport restoration across the tested hook exits.
- Movement-owned interpolation policy so a setting change affects new movement records without rewriting motion already in flight.
- Presentation-phase and allocation attribution tooling kept separate from clean timing.
- Measured proxy reservation after sorting and deduplicating candidate tiles.
- Reproducible native and standalone validation paths.

## Next proof boundary

The next milestone is matched live evidence, not another speculative rewrite.

1. Run control and candidate on the same temporary save and the same display settings.
2. Capture present intervals, simulation throughput, CPU frame time, and 1% lows whenever the display path exposes them.
3. Alternate AB and BA runs to separate build identity from scene order.
4. Check ordinary travel, dense crowds, hauling, stairs, doors, overlaps, multi-tile creatures, vehicles, camera motion, pause, resize, and zoom.
5. Restore the supported winning build and keep the exact hashes with the report.

The current controlled runtime readback is DF 0.53.16 / DFHack 53.16-r1.1 at 2560×1440 windowed, with simulation cap 120 and graphics cap 240. The candidate loaded successfully. A matched control/candidate perceptual result is still open.

## Engineering sequence

### 1. Clock and continuity

Keep all movement consumers on the same elapsed-time contract. Test duplicate timestamps, rollover, stale buffers, partial landings, additional scroll hints, and recovery whenever the clock path changes.

### 2. Indexed collection

Port further upstream indexing ideas only when exact fragment ownership, layer ordering, movement IDs, and companion matching remain unchanged. A faster lookup that changes a multi-tile endpoint is a regression.

### 3. Geometry

Audit fractional-pixel endpoints at every reachable zoom and downstream raster path. The current geometry passes the tested seams; no production defect has been demonstrated yet.

### 4. Rendering state

Keep SDL state guards small and explicit. Any new camera or world-effect pass must restore incoming clip, color, and viewport origin on normal and early-return paths.

### 5. Interpolation

Keep policy, duration, and phase stable for an individual movement. Explore additional easing only after the current invariant and matched live tests remain quiet.

### 6. Perceptual polish

Only after the proof boundary is green, consider optional camera settle, world-effect continuity, and subtle landing emphasis. These should clarify motion without changing game state or masking a frame-time problem.

## Explicitly out of scope for the current candidate

- A second simulation or prediction system
- Unbounded entity history or persistent scratch caches
- Arbitrary container multipliers
- Spring cameras, animated zoom, and UI animation
- Claims about sustained 240 presents/s or input latency without display evidence

## Contribution standard

Every performance change should identify its fixture, warmup, trial count, measured rows, compiler, and scope. Every visual change should identify zoom, tile width, viewport, movement class, and the failure mode it addresses. Keep rejected experiments and unfavorable tails visible.
