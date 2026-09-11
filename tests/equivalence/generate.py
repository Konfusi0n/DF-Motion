#!/usr/bin/env python3
"""Generate an offline test using exact frozen/current production collector bodies."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

BASELINE = "5a4c448440d732097ace2a0cb415d8762c0a0d30"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def block(source, marker, semicolon=False):
    """Extract one exact brace-delimited declaration, ignoring comments/literals."""
    start = source.index(marker)
    scrub = re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                   lambda m: " " * len(m.group()), source, flags=re.S)
    opening = scrub.index("{", start)
    depth = 0
    for end in range(opening, len(scrub)):
        depth += (scrub[end] == "{") - (scrub[end] == "}")
        if depth == 0:
            end += 1
            if semicolon:
                assert source[end] == ";"
                end += 1
            return source[start:end]
    raise ValueError("Unterminated declaration: " + marker)


def namespace(name, header, cpp):
    exact = [block(cpp, "struct render_proxyst", True),
             "using tile_coveragest=std::set<std::pair<int32_t,int32_t>>;",
             block(cpp, "struct render_coveragest", True),
             block(cpp, "constexpr uint16_t visual_layer_bit"),
             block(cpp, "std::vector<render_proxyst> collect_proxies("),
             block(cpp, "render_coveragest collect_coverage(")]
    return (f"\n#undef VISUAL_ANIMATION_H\nnamespace {name} {{\n" + header + r'''
namespace df { using graphic_viewportst=::Fixture; using renderer_2d_base=::Renderer; }
constexpr size_t visual_layer_count=static_cast<size_t>(viewport_visual_layer::count);
visual_animation_managerst animation_manager;
bool flip_enabled=true;
auto visual_layers(df::graphic_viewportst *vp,bool previous=false) {
    std::array<int32_t *,visual_layer_count> out{};
    for(size_t i=0;i<out.size();++i)out[i]=(previous?vp->old[i]:vp->now[i]).data();
    return out;
}
bool inside_clip(const df::graphic_viewportst *vp,int32_t x,int32_t y) {
    return x>=vp->clipx[0]&&x<=vp->clipx[1]&&y>=vp->clipy[0]&&y<=vp->clipy[1];
}
bool has_fire(const df::graphic_viewportst *vp,int32_t x,int32_t y) {
    return vp->fire.at(size_t(x*vp->dim_y+y))!=0;
}
SDL_Texture *cached_texture(df::renderer_2d_base *r,int32_t texpos) {
    r->calls.push_back(texpos);
    return r->fixture->missing.count(texpos)?nullptr:&textures.at(size_t(texpos));
}
void sync(Fixture &f,bool invalid=false) {
    viewport_visual_animation_inputst input;
    input.viewport=&f;input.dim_x=f.dim_x;input.dim_y=f.dim_y;
    input.context_revision=f.revision;input.pan_x=f.pan_x;input.pan_y=f.pan_y;
    for(size_t i=0;i<input.current.size();++i) {
        input.current[i]=f.now[i].data();input.previous[i]=f.old[i].data();
    }
    input.current_background=f.background.data();input.previous_background=f.background_old.data();
    if(invalid)input.current[0]=nullptr;
    f.screentexpos_old=f.old[1].data();
    animation_manager.synchronize_viewport(input);
}
''' + "\n".join(exact) + f"\n}} // namespace {name}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixed-modes", action="store_true",
                        help="Keep each trace's initial interpolation mode; mode-switch semantics have separate tests")
    parser.add_argument("--allow-unindexed", action="store_true",
                        help="Bootstrap harness only; does not validate an index implementation")
    args = parser.parse_args()
    repo = args.repo.resolve()
    files = {}
    for filename in ("visual_animation.h", "smooth-movement.cpp"):
        files["baseline/" + filename] = subprocess.run(
            ["git", "-C", str(repo), "show", BASELINE + ":" + filename],
            check=True, stdout=subprocess.PIPE).stdout
        files["candidate/" + filename] = (repo / filename).read_bytes()
    decoded = {key: value.decode("utf-8") for key, value in files.items()}
    indexed = all(name in decoded["candidate/visual_animation.h"]
                  for name in ("active_movement_tiles(", "mirrored_tiles("))
    if not indexed and not args.allow_unindexed:
        parser.error("Candidate index APIs are absent; use --allow-unindexed only for harness bootstrap")
    template = Path(__file__).with_name("trace.cpp.in").read_text(encoding="utf-8")
    # Load all standard headers globally before including either full header in its namespace.
    includes = set(re.findall(r"^#include\s+(<[^>]+>)", "\n".join(
        value for key, value in decoded.items() if key.endswith(".h")), re.M))
    includes.update("<" + name + ">" for name in (
        "iostream", "set", "unordered_map", "string", "utility", "cstdlib", "type_traits"))
    generated = "// Generated from exact source snapshots; see source-receipt.json.\n"
    generated += "\n".join("#include " + item for item in sorted(includes)) + "\n"
    preamble, driver = template.split("// INSERT_PRODUCTION_NAMESPACES_HERE", 1)
    generated += preamble
    for name in ("baseline", "candidate"):
        generated += namespace(name, decoded[name + "/visual_animation.h"],
                               decoded[name + "/smooth-movement.cpp"])
    generated += ("\n#define HAS_INDEX_API 1\n" if indexed else "\n#define HAS_INDEX_API 0\n")
    generated += "#define TRACE_FIXED_MODES " + str(int(args.fixed_modes)) + "\n"
    generated += driver
    args.output.mkdir(parents=True, exist_ok=True)
    output_cpp = args.output / "collector-equivalence.cpp"
    output_cpp.write_bytes(generated.encode("utf-8"))
    for name, data in files.items():
        dest = args.output / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    receipt = {"baseline_commit": BASELINE, "candidate_index_api_present": indexed,
               "interpolation_schedule": "fixed_per_trace" if args.fixed_modes else "legacy_mode_toggles",
               "reference_production_code_modified": False,
               "source_sha256": {name: digest(data) for name, data in files.items()},
               "generated_cpp_sha256": digest(output_cpp.read_bytes()),
               "generator_sha256": digest(Path(__file__).read_bytes()),
               "trace_template_sha256": digest(Path(__file__).with_name("trace.cpp.in").read_bytes()),
               "production_collector_bodies_modified": False,
               "boundaries": "Real manager/collector code; stubbed DF buffers, clip, fire, and texture lookup; no SDL draw or live game proof"}
    (args.output / "source-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
