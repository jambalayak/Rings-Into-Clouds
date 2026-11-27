#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Read-only XIP audit helpers. Never modifies firmware sources or generated assets."""
import argparse
import collections
import hashlib
import math
import pathlib
import re
import subprocess
import zlib

def run(args):
    return subprocess.run(args, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True).stdout

def symbol_rows(nm, paths):
    rows = []
    for path in paths:
        out = run([nm, "-S", "--size-sort", "--defined-only", str(path)])
        for line in out.splitlines():
            f = line.split()
            if len(f) >= 4:
                try: size = int(f[-3], 16)
                except ValueError: continue
                name = f[-1]
                if size >= 512:
                    rows.append((path, name, size))
    return rows

def strings_report(obj, out):
    sec = run([out, "-s", "-j", ".rodata.str1.1", str(obj)])
    data = bytearray()
    for line in sec.splitlines():
        m = re.match(r"\s*[0-9a-f]+\s+((?:[0-9a-f]{2}\s+)+)", line)
        if m: data.extend(bytes.fromhex(m.group(1)))
    strings = [x.decode("utf-8", "replace") for x in bytes(data).split(b"\0") if x]
    counts = collections.Counter(strings)
    with open("strings-report.txt", "w", encoding="utf-8") as f:
        f.write(f"section=.rodata.str1.1 extracted_bytes={len(data)} strings={len(strings)} unique={len(counts)}\n")
        for s,n in sorted(counts.items(), key=lambda x:(-x[1],x[0])):
            f.write(f"count={n}\t{s!r}\n")

def sample_report(objcopy, obj, symbol, out):
    raw = subprocess.run([objcopy, "--dump-section", f".rodata.SMP_DATA={out}",
                          str(obj)], text=True, capture_output=True)
    if raw.returncode:
        pathlib.Path(out).unlink(missing_ok=True)
        return
    b = pathlib.Path(out).read_bytes()
    if not b: return
    def entropy(x):
        c=collections.Counter(x); n=len(x)
        return -sum((v/n)*math.log2(v/n) for v in c.values())
    delta=bytes((b[i]-b[i-1])&255 for i in range(1,len(b)))
    with open("sample-data-estimates.txt","w") as f:
        f.write(f"bytes={len(b)}\n")
        f.write("storage=8-bit bytes; generator documents IMA ADPCM 4-bit samples packed two nibbles per byte\n")
        f.write(f"unique_byte_values={len(set(b))} byte_entropy={entropy(b):.5f} bits/byte\n")
        f.write(f"delta_entropy={entropy(delta):.5f} bits/byte\n")
        f.write(f"zlib9={len(zlib.compress(b,9))} ({100*len(zlib.compress(b,9))/len(b):.2f}%)\n")
        d=bytes((delta[1:] if False else delta))
        f.write(f"delta_zlib9={len(zlib.compress(d,9))} ({100*len(zlib.compress(d,9))/len(b):.2f}% of original)\n")
        f.write(f"bit_occupancy={[sum((v>>i)&1 for v in b) for i in range(8)]}\n")
        f.write("These are lossless estimates only; no sample format or firmware change.\n")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--nm",required=True); p.add_argument("--objdump",required=True)
    p.add_argument("--objcopy",required=True); p.add_argument("--objects",nargs="+",required=True)
    p.add_argument("--root",default=".")
    a=p.parse_args()
    paths=[pathlib.Path(x) for x in a.objects if pathlib.Path(x).is_file()]
    rows=symbol_rows(a.nm,paths)
    with open("symbol-size-report.txt","w") as f:
        for path,name,size in sorted(rows,key=lambda x:-x[2]):
            f.write(f"{size:8d}\t{path}\t{name}\n")
    by_hash=collections.defaultdict(list)
    for path,name,size in rows:
        if not any(k in name.lower() for k in ("lut","sine","window","data","table","fir","exp","smp","af_","kc_","ai")): continue
        # Locate a standalone symbol dump. objcopy extraction by section is intentionally
        # not guessed here: section offsets and symbol extents are in the accompanying ELF reports.
        by_hash[(path.name,name,size)].append((path,name))
    with open("table-symbol-inventory.txt","w") as f:
        f.write("Large candidate table symbols (>=512 B); exact content hashes require symbol-range extraction from ELF.\n")
        for path,name,size in sorted(rows,key=lambda x:-x[2]):
            if any(k in name.lower() for k in ("lut","sine","window","data","table","fir","exp","smp","af_","kc_","ai")):
                f.write(f"{size}\t{path}\t{name}\n")
    # A full object-level disassembly/relocation report accompanies this script. Source reader
    # locations are collected exactly (file:line) without modifying or preprocessing sources.
    root=pathlib.Path(a.root)
    patterns=re.compile(r"(lut_sine|lut_sin|lut_window|lut_sine_window_4096|SINE|FM6_EXP2|SMP_DATA)")
    with open("table-source-readers.txt","w") as f:
        for src in root.rglob("*"):
            if not src.is_file() or src.suffix not in (".c",".cc",".cpp",".h",".hpp"): continue
            try: lines=src.read_text(errors="replace").splitlines()
            except OSError: continue
            for i,line in enumerate(lines,1):
                if patterns.search(line): f.write(f"{src}:{i}: {line.strip()}\n")
    strings_report(paths[0],a.objdump) if paths else None
    print(f"symbol inventory: {len(rows)} symbols >=512 B across {len(paths)} object files")
    print("NOTE: exact hashes/subsets/symmetry require symbol byte extraction; this script deliberately does not infer symbol bytes from section dumps.")

if __name__=="__main__": main()
