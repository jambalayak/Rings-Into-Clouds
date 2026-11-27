#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""CI-workspace-only probe of the retained DRUM/SLICE per-part state budget.

The normal firmware source and engine allocation are not changed. This overlay
is applied only in the ephemeral diagnostic build after the engine-trim overlay.
"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]

def replace_once(path, old, new, label):
    p = root / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected exactly one match in {path}, found {n}")
    p.write_text(s.replace(old, new, 1))

# Four parts currently reserve 12,888 bytes each (51,552 bytes total).
# Test 8,192 bytes per part; retained-engine static assertions are the guard.
replace_once(
    "firmware/src/engines.c",
    "#define ENG_MEM_PART 12888u",
    "#define ENG_MEM_PART 8192u    /* RIC diagnostic candidate: DRUM + SLICE only */",
    "per-part engine memory candidate",
)

# The trimmed registry cannot select these engines. Their compile-time state
# assertions describe removed engines, not the active allocation requirement.
for path, old, label in [
    ("firmware/src/eng_phys.c",
     'ENG_MEM_FITS("PHYS", sizeof(phys_slot_t) * PHYS_POLY);   /* (it sets ENG_MEM_PART) */',
     "PHYS memory assertion"),
    ("firmware/src/eng_grain.c",
     'ENG_MEM_FITS("GRAIN", sizeof(gr_part_t));',
     "GRAIN memory assertion"),
    ("firmware/src/eng_fm6.c",
     'ENG_MEM_FITS("FM6", sizeof(fm6_note_t) * FM6_POLY);',
     "FM6 memory assertion"),
]:
    replace_once(path, old, "/* RIC diagnostic: removed engine; state is not selectable. */", label)

# Keep the retained engines' bounds checks active.
for path, token in [
    ("firmware/src/eng_drum.c", 'ENG_MEM_FITS("DRUM", sizeof(drum_lane_t) * DV_NLANE);'),
    ("firmware/src/eng_slice.c", 'ENG_MEM_FITS("SLICE", sizeof(slc_rbuf_t));'),
]:
    if token not in (root / path).read_text():
        raise SystemExit(f"retained engine memory assertion missing: {path}")

out = root / "build/rings-clouds-pool-sizing"
out.mkdir(parents=True, exist_ok=True)
report = """RINGS INTO CLOUDS POOL sizing diagnostic overlay
Base: rings-clouds-engine-trim-probe (isolated engine trim + sine-table fold)
Candidate ENG_MEM_PART: 8,192 bytes per part x 4 parts = 32,768 bytes
Previous ENG_MEM_PART: 12,888 bytes per part x 4 parts = 51,552 bytes
Potential shared engine-memory reduction: 18,784 bytes
Only DRUM and SLICE remain selectable; their ENG_MEM_FITS static assertions remain active.
PHYS, GRAIN and FM6 state assertions are suppressed only because those engines are tombstoned.
No audio routing, DSP behavior, presets, or normal source files are committed by this overlay.
This is a diagnostic link only; no .bin, .fwsc, OTA loader or installable package is generated.
"""
(out / "pool-sizing-report.txt").write_text(report)
print(report)
