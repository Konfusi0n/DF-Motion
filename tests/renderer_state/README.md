# Offscreen renderer-state tests

`test_renderer_state.cpp` includes the production `renderer_state.h` guards and
executes them with SDL 2.26.2's actual software renderer on a 64-by-64 ARGB surface.
It creates no window and initializes no video subsystem. No DFHack or game process
is required. Pixel readback copies the surface only after `SDL_RenderFlush`.

Provide the SDL 2.26.2 development headers and x64 import library. The native
Windows build uses MSVC with `/std:c++17 /EHsc /MD /O2 /UNDEBUG`, the repository
root and SDL include directory on the include path, and `SDL2.lib` at link time.
Zig can build the same source with `-target x86_64-windows-gnu -std=c++17 -O2
-UNDEBUG`, the same include paths, and that x64 import library. Place the matching
`SDL2.dll` beside the test executable. `SDL_MAIN_HANDLED` avoids SDL2main linkage.

The supported matrix covers disabled, enabled empty, disjoint, incoming clip
containing the map, map containing the incoming clip, and partially overlapping
clips at stable scales 1, 1.25, and 2, each with normal, nested, and early-return
exits. Tests check temporary replacement semantics, exact public clip
state, post-restoration pixels, RGBA restoration before repaint, both renderer
origin fields, and unchanged viewport, scale, blend mode, and render target.
A failing draw-color getter is injected while an outer clip guard is active;
the operation must return before drawing and preserve the caller's state.
Production intentionally aborts the plugin repaint when draw color cannot be
captured; writing a temporary color without a restorable snapshot would leak
state into the subsequent engine draw. The outer clip guard still restores on
that early return.

The clip contract requires the incoming clip to have been set under the current
scale, which must remain unchanged throughout the guard. Two intentional
out-of-contract diagnostics demonstrate SDL2's limitation: a clip set under an
older scale, and a scale change inside the guarded scope. Both retain the same
reported integer rectangle while producing different pixels. They are reported
as unsupported diagnostics, not successful restoration of SDL's hidden floating
state. The production guard never accesses SDL internals or changes scale.

The Stage 2 evidence also contains a separate header copy with only the clip
destructor's restore call omitted. The unmodified test must compile but fail
against that negative control on both native MSVC and Zig. Production files are
never modified to run this control.

This validates the shared guards and actual SDL software clipping behavior. It
does not establish live DF rendering, hardware-backend behavior, or game FPS.
