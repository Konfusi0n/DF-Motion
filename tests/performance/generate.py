#!/usr/bin/env python3
"""Snapshot exact production sources and emit a non-game comparison benchmark."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

BASELINE = "5a4c448440d732097ace2a0cb415d8762c0a0d30"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git(repo, *arguments):
    return subprocess.run(["git", "-C", str(repo), *arguments], check=True,
                          stdout=subprocess.PIPE).stdout


def generate(repo, output, baseline=BASELINE, candidate_commit=None, attribution=False):
    repo, output = Path(repo).resolve(), Path(output).resolve()
    if attribution and candidate_commit is None:
        raise ValueError("Diagnostic attribution requires an exact candidate commit")
    if not re.fullmatch(r"[0-9a-f]{40}", baseline):
        raise ValueError("Baseline must be an exact 40-character commit hash")
    if git(repo, "rev-parse", baseline + "^{commit}").decode().strip() != baseline:
        raise ValueError("Baseline does not resolve to the requested exact commit")
    if candidate_commit is not None:
        if not re.fullmatch(r"[0-9a-f]{40}", candidate_commit):
            raise ValueError("Candidate commit must be an exact 40-character hash")
        if git(repo, "rev-parse", candidate_commit + "^{commit}").decode().strip() != candidate_commit:
            raise ValueError("Candidate commit does not resolve exactly")
    helper = Path(__file__).resolve().parents[1] / "equivalence" / "generate.py"
    spec = importlib.util.spec_from_file_location("equivalence_extraction", helper)
    module = importlib.util.module_from_spec(spec)
    original_bytecode_setting = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = original_bytecode_setting
    files = {}
    for filename in ("visual_animation.h", "smooth-movement.cpp"):
        files["baseline/" + filename] = git(repo, "show", baseline + ":" + filename)
        files["candidate/" + filename] = (git(repo, "show", candidate_commit + ":" + filename)
                                          if candidate_commit else (repo / filename).read_bytes())
    decoded = {name: data.decode("utf-8") for name, data in files.items()}
    includes = set(re.findall(r"^#include\s+(<[^>]+>)", "\n".join(
        value for name, value in decoded.items() if name.endswith(".h")), re.M))
    includes.update("<" + name + ">" for name in (
        "chrono", "cstddef", "cstring", "iomanip", "iostream", "new", "optional", "set",
        "string", "type_traits", "unordered_map", "utility"))
    template_path = Path(__file__).with_name("benchmark.cpp.in")
    preamble, driver = template_path.read_text(encoding="utf-8").split(
        "// INSERT_PRODUCTION_NAMESPACES_HERE", 1)
    generated = "// Exact production bodies; see source-receipt.json.\n"
    generated += "\n".join("#include " + item for item in sorted(includes)) + "\n"
    generated += preamble
    manifests, instrumented = [], {}
    registry = []
    if attribution:
        import instrument
        registry = copy.deepcopy(instrument.SITES)
    for name in ("baseline", "candidate"):
        cpp = decoded[name + "/smooth-movement.cpp"]
        exact = [module.block(cpp, "struct render_proxyst", True),
                 "using tile_coveragest=std::set<std::pair<int32_t,int32_t>>;",
                 module.block(cpp, "struct render_coveragest", True),
                 module.block(cpp, "constexpr uint16_t visual_layer_bit"),
                 module.block(cpp, "std::vector<render_proxyst> collect_proxies("),
                 module.block(cpp, "render_coveragest collect_coverage(")]
        if attribution:
            exact[4], manifest = instrument.collector(cpp, exact[4], name, registry)
            manifests.append(manifest)
            instrumented[name + "-collect_proxies.cpp"] = exact[4]
            exact[5], manifest = instrument.coverage(cpp, exact[5], name, registry)
            manifests.append(manifest)
            instrumented[name + "-collect_coverage.cpp"] = exact[5]
        generated += (f"\n#undef VISUAL_ANIMATION_H\nnamespace {name} {{\n" +
                      decoded[name + "/visual_animation.h"])
        generated += r'''
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
    return vp->fire[size_t(x*vp->dim_y+y)]!=0;
}
SDL_Texture *cached_texture(df::renderer_2d_base *renderer,int32_t texpos) {
#if DF_MOTION_ATTRIBUTION
    attribution_probe::Scope texture(attribution_probe::Phase::texture_adapter,7);
#endif
    ++renderer->texture_calls;
    renderer->texture_hash=(renderer->texture_hash^uint32_t(texpos))*0x100000001b3ULL;
    return texpos>0&&size_t(texpos)<textures.size()?&textures[size_t(texpos)]:nullptr;
}
void sync(Fixture &fixture) {
    viewport_visual_animation_inputst input;
    input.viewport=&fixture;input.dim_x=fixture.dim_x;input.dim_y=fixture.dim_y;
    input.context_revision=fixture.revision;input.pan_x=fixture.pan_x;input.pan_y=fixture.pan_y;
    for(size_t layer=0;layer<input.current.size();++layer) {
        input.current[layer]=fixture.now[layer].data();input.previous[layer]=fixture.old[layer].data();
    }
    input.current_background=fixture.background.data();input.previous_background=fixture.background_old.data();
    animation_manager.synchronize_viewport(input);
}
'''
        generated += "\n".join(exact)
        generated += r'''
struct Engine {
    static constexpr const char *name="ENGINE_NAME";
    using Proxies=std::vector<render_proxyst>;
    using Coverage=render_coveragest;
    static void reset(){animation_manager=visual_animation_managerst{};}
    static void begin(uint32_t time){animation_manager.begin_frame(time);}
    static void synchronize(Fixture &fixture){sync(fixture);}
    static void end(){animation_manager.end_frame();}
    static Proxies proxies(Renderer &renderer,Fixture &fixture){return collect_proxies(&renderer,&fixture);}
    static Coverage coverage(const Proxies &proxies,int32_t height){return collect_coverage(proxies,height);}
};
} // namespace
'''.replace("ENGINE_NAME", name)
    generated += driver
    # Reserve the evidence directory atomically. Existing paths, even empty ones,
    # are rejected so concurrent invocations cannot share or replace an output.
    output.mkdir(parents=True, exist_ok=False)
    if attribution:
        (output / "attribution_probe.h").write_bytes(Path(__file__).with_name("attribution_probe.h").read_bytes())
        instrumented_output = output / "instrumented"
        instrumented_output.mkdir()
        for name, body in instrumented.items():
            (instrumented_output / name).write_text(body, encoding="utf-8", newline="")
        (output / "insertion-manifest.json").write_text(json.dumps({
            "sites": registry, "declarations": manifests,
            "scope": "Inserted diagnostic tags only; marker removal reconstructs pristine production declarations. Timers and allocation overrides perturb optimization and allocator behavior."}, indent=2) + "\n", encoding="utf-8")
    output_cpp = output / "presentation-performance.cpp"
    output_cpp.write_bytes(generated.encode("utf-8"))
    for name, data in files.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    receipt = {
        "baseline_commit": baseline,
        "candidate_head": git(repo, "rev-parse", "HEAD").decode().strip(),
        "candidate_commit": candidate_commit,
        "candidate_production_diff": [] if candidate_commit else git(repo, "diff", "--name-only", "HEAD", "--",
                                         "visual_animation.h", "smooth-movement.cpp").decode().splitlines(),
        "source_sha256": {name: sha256(data) for name, data in files.items()},
        "generated_cpp_sha256": sha256(output_cpp.read_bytes()),
        "generator_sha256": sha256(Path(__file__).read_bytes()),
        "template_sha256": sha256(template_path.read_bytes()),
        "equivalence_extraction_helper_sha256": sha256(helper.read_bytes()),
        "production_bodies_modified": attribution,
        "production_changes_are_insertion_only_diagnostic_markers": attribution,
        "scope": "Full production managers and exact collector/coverage bodies; allocation-free DF/texture adapters; no SDL draws, GPU, game, or FPS proof",
    }
    if attribution:
        receipt["attribution_probe_sha256"] = sha256((output / "attribution_probe.h").read_bytes())
        receipt["instrumenter_sha256"] = sha256(Path(__file__).with_name("instrument.py").read_bytes())
        receipt["insertion_manifest_sha256"] = sha256((output / "insertion-manifest.json").read_bytes())
    (output / "source-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", default=BASELINE)
    parser.add_argument("--candidate-commit")
    parser.add_argument("--attribution", action="store_true")
    arguments = parser.parse_args()
    print(json.dumps(generate(arguments.repo, arguments.output, arguments.baseline, arguments.candidate_commit, arguments.attribution), indent=2))
