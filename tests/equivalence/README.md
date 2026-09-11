# Offline collector equivalence

`generate.py` uses Python's standard library and invokes Git with a subprocess
argument list, never a shell. The reference is pinned to
`5a4c448440d732097ace2a0cb415d8762c0a0d30`. It reads that commit's complete
`visual_animation.h` and exact `render_proxyst`, `render_coveragest`, layer-bit,
`collect_proxies`, and `collect_coverage` declarations. The candidate comes from
the selected working tree. Reference and candidate production bodies are not
rewritten. Standard headers load outside the two namespaces.

From the repository root, generate into a dedicated evidence directory:

```text
python tests/equivalence/generate.py --repo . --output <evidence-output>
zig c++ -target x86_64-windows-gnu -std=c++17 -O2 -UNDEBUG <evidence-output>/collector-equivalence.cpp -o <evidence-output>/collector-equivalence.exe
<evidence-output>/collector-equivalence.exe
```

Use the workspace's verified portable Zig and process-scoped cache paths. Native
MSVC can compile the generated C++17 translation unit too. No DFHack build or game
is required. `--allow-unindexed` only bootstraps the harness; an `index_api=0`
result is not validation of an index port.

`source-receipt.json` records the full frozen commit, SHA-256 for both source
snapshots, generator/template hashes, and generated translation-unit hash. Raw
snapshots accompany the generated file, so results remain bound to the exact
candidate tested even if working files subsequently change.

The driver uses 100 fixed integer-PRNG seeds, 160 steps per seed, rectangular
grids, and both movement modes. Targeted traces exercise exact fragment anchors,
equal-motion/different-ID precedence at identical timestamps, predecessor
replacement, stalled/landed scrolls, expiry, cancellation, missing textures,
fire/clip rejection, resize/context reset, and unseen-viewport discard. All nine
layers and a one-tile out-of-bounds border are compared after each operation;
lookups are also compared after `begin_frame` before synchronization. Sparse
candidate completeness/append semantics and exact mirrored order are checked.

The duplicate-center fallback is exercised through public inputs: retain center
current/previous buffers describing one movement, then change a tracked background
element before expiry. A second active record at the same target is registered;
direct lookup retains the earlier ID while differing start times make nearby
designation companion lookup ambiguous. No friend declarations or private-state
injection are used.

PRNG draws assigning coordinates are explicitly sequenced before function calls.
The final trace fingerprint hashes the integer fixture data and frame settings;
its value and comparison counts should match across Zig and native MSVC builds.

Stage 1 also compares exact-buffer refresh using current and previous values in
every tracked layer, unchanged repetitions, different pointers with identical
bytes, mutations through unchanged pointers, and absent/partial/present background
pairs. Dense 32-by-24 and 7-by-5 viewports share a manager and alternate
synchronization order. Their traces include walking, idle interpolation, landed
scrolls, cancellation, invalidation, expiry, and equal-area dimension swaps.
The standalone manager suite independently asserts observable movement-ID
behavior for buffer refresh and verifies that repeated inputs still advance time.

The rejected Stage 1 experiment's evidence directory contains two deliberately broken candidate copies:
one trusts an existing snapshot without comparing bytes; the other retains stale
snapshot bytes after a change. Both must compile successfully and fail the oracle.
A separate forced-collision demonstration overrides only the reference signature
function with constant zero and checks that the reference misses a changed buffer
while the exact candidate detects it. This is controlled fault injection, **not a
naturally discovered FNV collision**. These mutations never enter production code.

For movement-owned interpolation policy, generate with `--fixed-modes`. Each
trace still exercises its initial linear or eased mode through the candidate's
captured-policy implementation. The random setter event and index invalidation
remain, and no PRNG draw or comparison is removed; only the mode toggle is
suppressed. The receipt and PASS line identify this schedule explicitly. The
reference production files remain exact `5a4c448`.

Mid-flight mode changes intentionally differ from the reference. The standalone
manager suite tests those changes with explicit expectations, including the
expired-eased predecessor boundary. A legacy-toggle differential failure is
not a fixed-mode regression; do not describe the new cross-mode behavior as
equivalent to the old global-policy behavior.

Comparisons include movement IDs and numeric fields, facing/scroll/follow/redraw
state, complete ordered proxy fields, per-proxy coverage, aggregate coverage and
selected masks, and exact texture-call order. The pass output reports comparison
counts and confirms nonzero moving-proxy and resting-mirror coverage.

The adapters stub DF viewport buffers, renderer texture lookup, clip predicates,
and fire flags. Texture identity is deterministic, and lookup failure is tested.
This executes the actual collector control flow but does not execute SDL draws,
DF allocation/ABI behavior, real texture-cache side effects, or game input. It
does not measure performance or establish live visual acceptance. Independent
gameplay and native plugin validation remain separate.
