#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""CI-workspace-only removal of the selectable SAMPLE engine.

The shared IMA user-slot infrastructure, SMP_DATA blob and SLICE source tables
remain intact. This overlay only removes SAMPLE's engine/editor/preset surface.
"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]

def replace_once(path, old, new, label):
    s = path.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected one match, found {n} in {path}")
    path.write_text(s.replace(old, new, 1))

engines = root / "firmware/src/engines.c"
core = root / "firmware/src/core.h"
graph = root / "firmware/src/ui_graph.c"
ui = root / "firmware/src/ui.c"
params = root / "firmware/src/params.c"

# Preserve engine ID 4 as a tombstone. IDs 10 and 13 remain DRUM and SLICE.
replace_once(engines, '    &ENG_SAMPLE,                 /* 4 SAMPLE retained for SLICE */',
             '    &RIC_ENGINE_REMOVED,         /* 4 SAMPLE retired; serialized ID preserved */',
             "SAMPLE registry tombstone")

# SLICE's missing-source notification is the only remaining notification path.
replace_once(engines,
'''    uint32_t si = (uint32_t)t->p[P_E0] % SMP_NALL;
#if FELUCCA_SLICE
    if (e == &ENG_SLICE) {
        si = slc_src_of(t->p);
        *code = 64u + si;
        return slc_get(si) ? 0 : N_SLC_SRC[si];
    }
#endif
    if (e != &ENG_SAMPLE)
        return 0;
    *code = 1u + si % 32u;
    return smp_set_missing(si) ? SMP_ALL_NAMES[si] : 0;''',
'''#if FELUCCA_SLICE
    if (e == &ENG_SLICE) {
        uint32_t si = slc_src_of(t->p);
        *code = 64u + si;
        return slc_get(si) ? 0 : N_SLC_SRC[si];
    }
#endif
    (void)code;
    return 0;''',
             "SAMPLE missing-source path")

replace_once(engines,
'''static const uint8_t ENGINE_ORDER[NENG_SHOWN] = {
    4,                           /* SAMPLE */
#if FELUCCA_SLICE
    13,                          /* SLICE */
#endif
    10,                          /* DRUM */
};''',
'''static const uint8_t ENGINE_ORDER[NENG_SHOWN] = {
#if FELUCCA_SLICE
    13,                          /* SLICE */
#endif
    10,                          /* DRUM */
};''',
             "SAMPLE editor order")
replace_once(engines,
             'static int eng_ok(uint32_t e) { return e == 4u || e == 10u || (FELUCCA_SLICE && e == 13u); }',
             'static int eng_ok(uint32_t e) { return e == 10u || (FELUCCA_SLICE && e == 13u); }',
             "SAMPLE selectable predicate")
replace_once(engines,
             '        e = 4u;                                  /* diagnostic fallback: retained SAMPLE slot */',
             '        e = 10u;                                 /* fallback to retained DRUM slot */',
             "engine rank fallback")
replace_once(core,
             '#define NENG_SHOWN 3u             /* RIC diagnostic profile: SAMPLE, SLICE, DRUM */',
             '#define NENG_SHOWN 2u             /* RIC profile: SLICE, DRUM */',
             "visible engine count")

# Remove SAMPLE-only waveform cache, decoder and graph. SLICE's waveform renderer
# immediately follows this block and is deliberately retained.
g = graph.read_text()
start_marker = "/* One shared, reduced sample display. Decode only in the UI/main loop with a"
end_marker = "#if FELUCCA_SLICE\n/* SLICES (ui_slice.c)"
start = g.find(start_marker)
end = g.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("could not isolate SAMPLE waveform block in ui_graph.c")
g = g[:start] + g[end:]
g = g.replace('    if (pg->scope == SC_ENGINE && ENGINES[t->eng_req % NENGINES] == &ENG_SAMPLE) h ^= sample_wave.pos * 13u + sample_wave.key;\n', '')
g = g.replace('    if (!ui.home && pg->scope == SC_ENGINE && ENGINES[t->eng_req % NENGINES] == &ENG_SAMPLE) sample_wave_tick(t);\n', '')
g = g.replace('            else if (pg->scope == SC_ENGINE && ENGINES[t->eng_req % NENGINES] == &ENG_SAMPLE && sample_wave.ready) graph_sample(c);\n', '')
if "sample_wave" in g or "graph_sample" in g:
    raise SystemExit("SAMPLE waveform references remain in ui_graph.c")
graph.write_text(g)

# Remove SAMPLE-specific preset alias browsing. Keep the legacy PERC -> DRUM
# migration in apply_preset_to/core.h for old projects and user presets.
replace_once(ui,
'''static uint32_t preset_orig(const engine_t *e, uint32_t k)
{
    return e->presets == SMP_PRESET_TABLE && k < SMP_NSETS ? SMP_SET_ORIG[k] : k;
}''',
'''static uint32_t preset_orig(const engine_t *e, uint32_t k)
{
    (void)e;
    return k;
}''',
             "SAMPLE preset alias mapping")
replace_once(ui,
'''static uint32_t preset_rank(const engine_t *e, uint32_t k)
{
    uint32_t i, n = 0;
    if (e->presets != SMP_PRESET_TABLE)
        return k;
    for (i = 0; i < k; i++)
        n += preset_orig(e, i) == i;
    return n;
}''',
'''static uint32_t preset_rank(const engine_t *e, uint32_t k)
{
    (void)e;
    return k;
}''',
             "SAMPLE preset rank")
replace_once(ui,
             '#define preset_shown(e) (ENGINES[e]->npresets - (ENGINES[e]->presets == SMP_PRESET_TABLE ? SMP_NALIAS : 0u))',
             '#define preset_shown(e) (ENGINES[e]->npresets)',
             "SAMPLE preset count")

replace_once(params,
'''    return d->names == SMP_ALL_NAMES && v >= 0 && v < SMP_NSETS ? SMP_SET_ORIG[v] : v;''',
'''    return v;''',
             "SAMPLE enum alias mapping")

# Expose compile-time engine memory sizes in felucca.o for a read-only POOL
# report. This does not change ENG_MEM_PART or the allocated POOL region.
needle = '#if FELUCCA_ADPCM\n#include "eng_adpcm.c"'
probe = '''__attribute__((used)) const uint32_t RIC_MEM_DRUM_BYTES = sizeof(drum_lane_t) * DV_NLANE;
#if FELUCCA_SLICE
__attribute__((used)) const uint32_t RIC_MEM_SLICE_BYTES = sizeof(slc_rbuf_t);
#else
__attribute__((used)) const uint32_t RIC_MEM_SLICE_BYTES = 0u;
#endif
__attribute__((used)) const uint32_t RIC_MEM_PART_BYTES = sizeof(eng_mem[0].b);

'''
# Insert after all engine source units are included and before the engine registry.
replace_once(engines,
             '/* the editor protocol, user presets and projects store these indices: append, never reorder */',
             probe + '/* the editor protocol, user presets and projects store these indices: append, never reorder */',
             "POOL size probes")

out = root / "build/rings-clouds-no-sample"
out.mkdir(parents=True, exist_ok=True)
(out / "overlay-report.txt").write_text("""RINGS INTO CLOUDS no-SAMPLE diagnostic overlay
Selectable engines: SLICE (13), DRUM (10); SAMPLE ID 4 remains a tombstone.
Removed only the SAMPLE engine selection, renderer, waveform UI and SAMPLE preset browser.
Retained: SMP_DATA byte-for-byte and at its original offsets; SLC_BREAK; SLC_PIANO;
SAMPLE/SLICE shared IMA decoder tables, sine fallback, user-slot scanner, user uploads,
user-slot flash format, SLICE manual-slice storage, DRUM and DV_KIT.
Retained legacy SAMPLE/PERC -> DRUM migration for old projects and user presets.
No SLICE or DRUM source/data/behavior edits.
No Rings/Clouds routing edits. No installable outputs are generated.
POOL allocation is measured only; ENG_MEM_PART is not modified.
""")
print((out / "overlay-report.txt").read_text(), end="")
