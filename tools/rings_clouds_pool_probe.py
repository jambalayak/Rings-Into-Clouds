#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Read the used compile-time DRUM/SLICE memory-size probes from felucca.o."""
import struct
import sys
from pathlib import Path
from elftools.elf.elffile import ELFFile

path = Path(sys.argv[1] if len(sys.argv) > 1 else "build/felucca.o")
wanted = {"RIC_MEM_DRUM_BYTES", "RIC_MEM_SLICE_BYTES", "RIC_MEM_PART_BYTES"}
found = {}
with path.open("rb") as f:
    elf = ELFFile(f)
    symtab = elf.get_section_by_name(".symtab")
    if symtab is None:
        raise SystemExit("no ELF symbol table in " + str(path))
    for sym in symtab.iter_symbols():
        if sym.name not in wanted:
            continue
        sec = elf.get_section(sym["st_shndx"])
        off = int(sym["st_value"])
        data = sec.data()[off:off + 4]
        if len(data) != 4:
            raise SystemExit("invalid probe symbol " + sym.name)
        found[sym.name] = struct.unpack("<I", data)[0]
missing = wanted - found.keys()
if missing:
    raise SystemExit("missing POOL probe symbols: " + ", ".join(sorted(missing)))
drum = found["RIC_MEM_DRUM_BYTES"]
slice_ = found["RIC_MEM_SLICE_BYTES"]
part = found["RIC_MEM_PART_BYTES"]
need = max(drum, slice_)
print("POOL remaining-engine allocation probe")
print(f"DRUM engine state: {drum} B per part")
print(f"SLICE reverse-window state: {slice_} B per part")
print(f"Minimum shared ENG_MEM_PART for DRUM + SLICE: {need} B per part")
print(f"Current ENG_MEM_PART: {part} B per part")
print(f"Current engine-memory POOL allocation: {part * 4} B (NPART=4)")
print(f"Potential per-part headroom above measured minimum: {part - need} B")
if part < need:
    raise SystemExit("current ENG_MEM_PART is smaller than a retained engine requirement")
