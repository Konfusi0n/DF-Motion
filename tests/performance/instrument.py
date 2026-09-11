#!/usr/bin/env python3
"""Insert diagnostic markers into copied declarations; never edit production files."""
import hashlib
import re

SITES = [
    {"id": 0, "name": "unattributed"},
    {"id": 1, "name": "synchronization.aggregate"},
    {"id": 2, "name": "collector.return_and_wrapper"},
    {"id": 3, "name": "coverage.return_and_wrapper"},
    {"id": 4, "name": "returned_proxies.destruction"},
    {"id": 5, "name": "returned_coverage.destruction"},
    {"id": 6, "name": "manager.teardown"},
    {"id": 7, "name": "texture.fixture_adapter_only"},
]


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Instrumentation:
    def __init__(self, source, declaration, namespace, function, registry):
        self.source, self.original = source, declaration
        self.namespace, self.function = namespace, function
        self.registry, self.insertions, self.counter = registry, [], 0
        self.base = source.index(declaration)

    def location(self, token, occurrence=0, expected=1):
        matches = [m.start() for m in re.finditer(re.escape(token), self.original)]
        if len(matches) != expected:
            raise ValueError(f"{self.function}: expected {expected} occurrences of {token!r}, found {len(matches)}")
        return matches[occurrence]

    def site(self, name, start, end):
        existing = next((entry for entry in self.registry if entry["name"] == name), None)
        if existing is None:
            existing = {"id": len(self.registry), "name": name, "locations": []}
            self.registry.append(existing)
        existing.setdefault("locations", []).append({
            "namespace": self.namespace, "file": "smooth-movement.cpp", "function": self.function,
            "line": self.source.count("\n", 0, self.base + start) + 1,
            "source_expression": self.original[start:end], "source_expression_sha256": digest(self.original[start:end])})
        if existing["id"] >= 64:
            raise ValueError("Diagnostic site registry exceeds its fixed capacity")
        return existing["id"]

    def add(self, offset, text, name):
        self.insertions.append({"offset": offset, "text": text, "name": name, "sequence": len(self.insertions)})

    def span(self, start, end, name, phase=None, declaration=False):
        site = self.site(name, start, end)
        variable = f"dfmotion_probe_{self.counter}"
        self.counter += 1
        constructor = (f"attribution_probe::Scope {variable}(attribution_probe::Phase::{phase},{site});"
                       if phase else f"attribution_probe::SiteScope {variable}({site});")
        if declaration:
            self.add(start, "\n" + constructor + "\n", name)
            self.add(end, f"\n{variable}.finish();\n", name)
        else:
            self.add(start, "{\n" + constructor + "\n", name)
            self.add(end, "\n}\n", name)

    def statement(self, token, name, occurrence=0, expected=1, phase=None, declaration=False):
        start = self.location(token, occurrence, expected)
        end = self.original.index(";", start) + 1
        self.span(start, end, name, phase, declaration)

    def finish(self):
        parts, manifest, previous, length = [], [], 0, 0
        for entry in sorted(self.insertions, key=lambda item: (item["offset"], item["sequence"])):
            text = self.original[previous:entry["offset"]]
            parts.extend((text, entry["text"]))
            length += len(text)
            manifest.append({**entry, "generated_start": length, "generated_end": length + len(entry["text"])})
            length += len(entry["text"])
            previous = entry["offset"]
        parts.append(self.original[previous:])
        generated = "".join(parts)
        restored, previous = [], 0
        for entry in manifest:
            if generated[entry["generated_start"]:entry["generated_end"]] != entry["text"]:
                raise ValueError("Insertion manifest does not match generated text")
            restored.append(generated[previous:entry["generated_start"]])
            previous = entry["generated_end"]
        restored.append(generated[previous:])
        if "".join(restored) != self.original:
            raise ValueError("Removing instrumentation did not reconstruct the pristine declaration")
        return generated, {"namespace": self.namespace, "function": self.function,
                           "pristine_sha256": digest(self.original), "instrumented_sha256": digest(generated),
                           "removal_reconstructs_pristine": True, "insertions": manifest}


def collector(source, declaration, namespace, registry):
    edit = Instrumentation(source, declaration, namespace, "collect_proxies", registry)
    start = edit.location("std::vector<int32_t> candidate_tiles;")
    end = edit.location("std::sort(candidate_tiles.begin(),candidate_tiles.end());")
    edit.span(start, end, "candidates.generate_and_convert", "candidate_generation", True)
    start = end
    end = edit.location("// The center layer is painted first.")
    edit.span(start, end, "candidates.sort_unique", "sort_unique", True)
    edit.statement("std::vector<int32_t> center_proxy_at", "centers.table_initialize", phase="center_anchor", declaration=True)
    anchor = edit.location("const auto anchor_matches=[&](")
    anchor_body = declaration.index("{", anchor) + 1
    site = edit.site("centers.anchor_lookup", anchor, anchor_body)
    edit.add(anchor_body, f"\nattribution_probe::Scope dfmotion_anchor(attribution_probe::Phase::center_anchor,{site});\n", "centers.anchor_lookup")
    start = edit.location("for(uint8_t draw_order=0;draw_order<visual_layer_count;++draw_order)", expected=2)
    end = edit.location("// A creature that has stopped")
    edit.span(start, end, "moving.loop", "moving_proxy", True)
    edit.statement("render_proxyst proxy=", "moving.proxy_construct", expected=2, declaration=True)
    edit.statement("proxy.coverage.emplace(coverage_x,coverage_y)", "moving.coverage_emplace")
    edit.statement("std::set<std::pair<int32_t,int32_t>> mirrored_coverage;", "moving.mirror_set_construct", declaration=True)
    edit.statement("mirrored_coverage.emplace(", "moving.mirror_set_emplace")
    edit.statement("proxy.coverage.insert(tile)", "moving.mirror_union_insert")
    edit.statement("proxies.push_back(std::move(proxy))", "moving.proxy_vector_push", expected=2)
    edit.statement("center_proxy_at[size_t(index)]=", "centers.accepted_write", phase="center_anchor")
    resting = edit.location("if(flip_enabled)")
    body = declaration.index("{", resting) + 1
    site = edit.site("resting.loop", resting, body)
    edit.add(body, f"\nattribution_probe::Scope dfmotion_resting(attribution_probe::Phase::resting_mirrored,{site});\n", "resting.loop")
    edit.statement("std::set<std::pair<uint8_t,int32_t>> drawn;", "resting.drawn_set_construct", declaration=True)
    edit.statement("drawn.emplace(", "resting.drawn_seed", expected=2)
    edit.statement("if(drawn.count(", "resting.drawn_lookup")
    edit.statement("render_proxyst proxy=", "resting.proxy_construct", occurrence=1, expected=2, declaration=True)
    edit.statement("proxy.coverage.emplace(coverage_x,y)", "resting.coverage_emplace")
    edit.statement("proxies.push_back(std::move(proxy))", "resting.proxy_vector_push", occurrence=1, expected=2)
    edit.statement("drawn.emplace(", "resting.drawn_insert", occurrence=1, expected=2)
    return edit.finish()


def coverage(source, declaration, namespace, registry):
    edit = Instrumentation(source, declaration, namespace, "collect_coverage", registry)
    edit.statement("render_coveragest coverage;", "coverage.container_construct", declaration=True)
    edit.statement("coverage.all.insert(", "coverage.all_insert")
    edit.statement("coverage.selected[", "coverage.selected_index")
    edit.statement("group.insert(", "coverage.group_insert")
    return edit.finish()
