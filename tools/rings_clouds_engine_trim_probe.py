#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""CI-workspace-only engine registry trim for a diagnostic Rings/Clouds build.

This keeps serialized engine IDs and the engine table's fixed length. Removed
indices point to one inert descriptor; SAMPLE, DRUM and SLICE remain selectable.
No production source is changed by this script outside the ephemeral CI checkout.
"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
engines = root / "firmware/src/engines.c"
core = root / "firmware/src/core.h"
e = engines.read_text()
c = core.read_text()

def replace_once(source, old, new, label):
    n = source.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {n}")
    return source.replace(old, new, 1)

# A single inert descriptor preserves every legacy engine number in ENGINES[].
marker = "/* the editor protocol, user presets and projects store these indices: append, never reorder */"
placeholder = '/* RIC diagnostic tombstone: engine IDs remain stable, but this engine is not selectable. */\nstatic const engine_t RIC_ENGINE_REMOVED = {.name = "OFF"};\n\n'
e = replace_once(e, marker, placeholder + marker, "tombstone insertion")

start = e.index("static const engine_t *const ENGINES[NENGINES] = {")
end = e.index("\n};", start) + len("\n};")
registry = """static const engine_t *const ENGINES[NENGINES] = {
    &RIC_ENGINE_REMOVED,         /* 0 ANALOG retired in this diagnostic profile */
    &RIC_ENGINE_REMOVED,         /* 1 DIGITAL reserved */
    &RIC_ENGINE_REMOVED,         /* 2 PHASE */
    &RIC_ENGINE_REMOVED,         /* 3 LOFI */
    &ENG_SAMPLE,                 /* 4 SAMPLE retained for SLICE */
    &RIC_ENGINE_REMOVED,         /* 5 FORMANT */
    &RIC_ENGINE_REMOVED,         /* 6 TRIO */
    &RIC_ENGINE_REMOVED,         /* 7 WHEEL */
    &RIC_ENGINE_REMOVED,         /* 8 GRAIN */
    &RIC_ENGINE_REMOVED,         /* 9 PHYS */
    &ENG_DRUM,                   /* 10 DRUM */
    &RIC_ENGINE_REMOVED,         /* 11 NOISE */
    &RIC_ENGINE_REMOVED,         /* 12 FM6 */
#if FELUCCA_SLICE
    &ENG_SLICE,                  /* 13 SLICE retained */
#endif
#if FELUCCA_ADPCM
    &ENG_ADPCM,                  /* 14 unchanged optional engine */
#endif
};"""
e = e[:start] + registry + e[end:]

# The sample-missing notification must no longer keep GRAIN's descriptor live.
old = """    if (e != &ENG_SAMPLE && e != &ENG_GRAIN)
        return 0;
    *code = (e == &ENG_GRAIN ? 32u : 1u) + si % 32u;"""
new = """    if (e != &ENG_SAMPLE)
        return 0;
    *code = 1u + si % 32u;"""
e = replace_once(e, old, new, "sample notification dependency")

# Only the retained engines are offered in the editor / preset browser.
start = e.index("static const uint8_t ENGINE_ORDER[NENG_SHOWN] = {")
end = e.index("\n};", start) + len("\n};")
order = """static const uint8_t ENGINE_ORDER[NENG_SHOWN] = {
    4,                           /* SAMPLE */
#if FELUCCA_SLICE
    13,                          /* SLICE */
#endif
    10,                          /* DRUM */
};"""
e = e[:start] + order + e[end:]

old = "static int eng_ok(uint32_t e) { return e < NENGINES && (FELUCCA_FM4 || e != ENGI_DIGITAL); }"
new = "static int eng_ok(uint32_t e) { return e == 4u || e == 10u || (FELUCCA_SLICE && e == 13u); }"
e = replace_once(e, old, new, "selectable engine predicate")
old = "        e = ENGI_FM6;                            /* (DIGITAL without FELUCCA_FM4: its sounds play as FM6) */"
new = "        e = 4u;                                  /* diagnostic fallback: retained SAMPLE slot */"
e = replace_once(e, old, new, "engine rank fallback")

# The display count matches the retained list; IDs themselves are not renumbered.
old = "#define NENG_SHOWN (NENGINES - !FELUCCA_FM4)"
new = "#define NENG_SHOWN 3u             /* RIC diagnostic profile: SAMPLE, SLICE, DRUM */"
c = replace_once(c, old, new, "visible engine count")

engines.write_text(e)
core.write_text(c)

out = root / "build/rings-clouds-engine-trim"
out.mkdir(parents=True, exist_ok=True)
report = """RINGS INTO CLOUDS engine-trim diagnostic overlay
Base: rings-sine-table-fold-probe (sine-table fold retained as an isolated experiment)
Selectable engines: SAMPLE (4), DRUM (10), SLICE (13)
Tombstoned IDs: ANALOG 0, DIGITAL 1, PHASE 2, LOFI 3, FORMANT 5, TRIO 6,
WHEEL 7, GRAIN 8, PHYS 9, NOISE 11, FM6 12
Serialized engine indices and ENGINES[] length are preserved; no renumbering.
SAMPLE remains available to SLICE. DRUM and SLICE remain registered.
Legacy PHYS->DRUM and SAMPLE/PERC migration code is untouched.
No Rings/Clouds audio routing is added by this experiment.
The overlay is applied only in the ephemeral GitHub Actions workspace.
No firmware source in the repository is modified by this script at runtime.
No .bin, .fwsc, OTA loader or installable package is generated.
"""
(out / "overlay-report.txt").write_text(report)
print(report)
