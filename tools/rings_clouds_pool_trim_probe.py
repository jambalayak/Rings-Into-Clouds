#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""CI-workspace-only DRUM/SLICE engine-memory allocation probe.

Reduces the shared per-part engine state to the measured DRUM requirement.
Removed engine descriptors remain tombstoned by the preceding overlays; their
compile-time ENG_MEM_FITS checks are disabled only in this ephemeral profile.
Explicit assertions below protect the two retained engines.
"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = root / "firmware/src/engines.c"
s = p.read_text()

old = "#define ENG_MEM_PART 12888u"
if s.count(old) != 1:
    raise SystemExit(f"expected one 12888-byte allocation, found {s.count(old)}")
s = s.replace(old, "#define ENG_MEM_PART 1824u", 1)

old = '#define ENG_MEM_FITS(name, size) _Static_assert((size) <= ENG_MEM_PART, name " state over ENG_MEM_PART")'
if s.count(old) != 1:
    raise SystemExit("could not locate engine memory fit assertion macro")
s = s.replace(old, "#define ENG_MEM_FITS(name, size) /* removed engines are tombstoned in this profile */", 1)

needle = "__attribute__((used)) const uint32_t RIC_MEM_DRUM_BYTES = sizeof(drum_lane_t) * DV_NLANE;"
if s.count(needle) != 1:
    raise SystemExit("expected DRUM size probe from no-SAMPLE overlay")
asserts = """_Static_assert(sizeof(drum_lane_t) * DV_NLANE == 1824u,
               "measured DRUM state changed: re-audit ENG_MEM_PART");
_Static_assert(sizeof(slc_rbuf_t) <= 1824u,
               "SLICE reverse-window state exceeds retained engine allocation");
"""
s = s.replace(needle, asserts + needle, 1)
p.write_text(s)

out = root / "build/rings-clouds-pool-trim"
out.mkdir(parents=True, exist_ok=True)
(out / "allocation-report.txt").write_text(
    "RINGS INTO CLOUDS DRUM/SLICE engine-memory allocation probe\n"
    "Old ENG_MEM_PART: 12,888 bytes x 4 parts = 51,552 bytes\n"
    "Candidate ENG_MEM_PART: 1,824 bytes x 4 parts = 7,296 bytes\n"
    "Candidate POOL recovery: 44,256 bytes\n"
    "Retained-state assertions: DRUM exactly 1,824 bytes; SLICE <= 1,824 bytes\n"
    "Only DRUM (engine 10) and SLICE (engine 13) remain selectable.\n"
    "Removed engine descriptors remain tombstones; serialized IDs unchanged.\n"
    "Allocation change applies only to ephemeral CI workspace.\n"
    "No DRUM/SLICE source or data changed; no installable output generated.\n"
)
print((out / "allocation-report.txt").read_text(), end="")
