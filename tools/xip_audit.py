#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Read-only XIP table, string, reader and sample-data audit. Requires pyelftools."""
import argparse, collections, hashlib, math, pathlib, re, struct, zlib, bz2, lzma, io
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection

EXT={".c",".cc",".cpp",".h",".hpp",".S"}
def getbytes(elf,s):
    n=s["st_shndx"]
    if not isinstance(n,int) or n>=elf.num_sections(): return None
    sec=elf.get_section(n)
    if sec["sh_type"]=="SHT_NOBITS": return None
    off=int(s["st_value"])-(int(sec["sh_addr"]) if elf.header["e_type"]!="ET_REL" else 0)
    size=int(s["st_size"]); d=sec.data()
    return d[off:off+size] if 0<=off and off+size<=len(d) and size else None
def ent(d):
    c=collections.Counter(d); n=len(d)
    return -sum(v/n*math.log2(v/n) for v in c.values()) if n else 0
def syms(path):
    elf=ELFFile(io.BytesIO(path.read_bytes())); tab=elf.get_section_by_name(".symtab")
    if not tab:return [],None
    rows=[]
    for s in tab.iter_symbols():
        if not s.name or int(s["st_size"])<512:continue
        d=getbytes(elf,s)
        if d is None:continue
        sec=elf.get_section(s["st_shndx"])
        if sec.name.startswith(".rodata") and sec.name!=".rodata.str1.1":
            rows.append((path,s.name,sec.name,d))
    return rows,(elf,tab)
def symmetries(d):
    out=[]
    if d==d[::-1]:out.append("byte mirror exact")
    for w,fmt,label in ((2,"h","int16"),(4,"i","int32"),(4,"f","float32")):
        if len(d)%w:continue
        a=struct.unpack("<"+fmt*(len(d)//w),d); n=len(a)
        if n<4:continue
        eq=lambda x,y: (abs(x-y)<1e-6 if fmt=="f" else x==y)
        if all(eq(a[i],a[n-1-i]) for i in range(n//2)):out.append(label+(" mirror approximate" if fmt=="f" else " mirror exact"))
        if all(eq(a[i],-a[n-1-i]) for i in range(n//2)):out.append(label+(" sign-mirror approximate" if fmt=="f" else " sign-mirror exact"))
        if n%2==0 and all(eq(a[i],-a[i+n//2]) for i in range(n//2)):out.append(label+(" half-wave sign flip approximate" if fmt=="f" else " half-wave sign flip exact"))
        if n%4==0:
            q=n//4
            if all(eq(a[i],a[q-i]) for i in range(1,q)):out.append(label+(" quarter-wave mirror approximate" if fmt=="f" else " quarter-wave mirror exact"))
    return out or ["no tested exact symmetry"]
def string_rows(path,elf,tab,sec):
    idx=next(i for i in range(elf.num_sections()) if elf.get_section(i).name==sec.name)
    refs=collections.defaultdict(list)
    for rs in elf.iter_sections():
        if not isinstance(rs,RelocationSection):continue
        tgt=elf.get_section(int(rs["sh_info"])); st=elf.get_section(int(rs["sh_link"]))
        for r in rs.iter_relocations():
            j=int(r["r_info_sym"])
            if j>=st.num_symbols():continue
            ts=st.get_symbol(j)
            if ts["st_shndx"]!=idx:continue
            off=int(ts["st_value"])+(int(r["r_addend"]) if r.is_RELA() else 0)
            fn=""
            for s in tab.iter_symbols():
                if s["st_shndx"]==int(rs["sh_info"]) and int(s["st_size"]) and int(s["st_value"])<=int(r["r_offset"])<int(s["st_value"])+int(s["st_size"]):
                    fn=s.name;break
            refs[off].append(f"{tgt.name}:{fn or '<section>'}")
    pos=0; out=[]
    for b in sec.data().split(b"\0"):
        if b:out.append((pos,b.decode("utf-8","replace"),refs.get(pos,[])))
        pos+=len(b)+1
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--objects",nargs="+",required=True);ap.add_argument("--root",default=".");a=ap.parse_args()
    allrows=[]; stringsets=[]; sample=None
    for x in a.objects:
        p=pathlib.Path(x)
        if not p.is_file():continue
        try:
            rows,pair=syms(p);allrows+=rows
            if pair:
                elf,tab=pair; sec=elf.get_section_by_name(".rodata.str1.1")
                if sec:stringsets.append((p,elf,tab,sec))
                sm=tab.get_symbol_by_name("SMP_DATA")
                if sm:sample=getbytes(elf,sm[0])
        except Exception as e:print("SKIP",p,e)
    hashes=collections.defaultdict(list)
    with open("xip-table-hashes.txt","w") as f:
        for p,n,s,d in allrows:
            h=hashlib.sha256(d).hexdigest();hashes[h].append((p,n,len(d)))
            f.write(f"{len(d)}\t{h}\t{s}\t{p}\t{n}\n")
    with open("xip-identical-duplicates.txt","w") as f:
        groups=[g for g in hashes.values() if len(g)>1]
        f.write("No duplicates found.\n" if not groups else "")
        for g in groups:
            f.write("BYTE-IDENTICAL\n")
            for p,n,z in g:f.write(f"  {p}\t{n}\t{z} B\n")
    relations=[]
    for p,n,s,d in allrows:
        for q,m,t,e in allrows:
            if (p,n)==(q,m) or len(d)>=len(e):continue
            if e.startswith(d):relations.append(f"PREFIX {n} in {m} ({p} -> {q})")
            for w in (1,2,4):
                if len(d)%w or len(e)%w:continue
                aa=[d[i:i+w] for i in range(0,len(d),w)];bb=[e[i:i+w] for i in range(0,len(e),w)]
                for st in range(2,9):
                    if len(bb[::st])==len(aa) and bb[::st]==aa:relations.append(f"STRIDE-{st} x {w*8}-bit {n} from {m}")
    pathlib.Path("xip-subsets.txt").write_text("\n".join(sorted(set(relations)) or ["No exact prefix/stride relations found."])+"\n")
    with open("xip-symmetry.txt","w") as f:
        for p,n,s,d in allrows:
            if any(k in n.lower() for k in ("sine","window")):f.write(f"{p} {n} {len(d)} B: {', '.join(symmetries(d))}\n")
    names=set()
    for p,n,s,d in allrows:
        names.add(n)
        names.update(re.findall(r"(?:lut_[A-Za-z0-9_]+|SMP_DATA|[A-Z][A-Z0-9_]{3,})",n))
    pat=re.compile(r"\\b(?:"+"|".join(re.escape(n) for n in sorted(names,key=len,reverse=True) if n)+r")\\b")
    with open("xip-table-readers.txt","w") as f:
        roots=[pathlib.Path(a.root)/"firmware",pathlib.Path(a.root)/"third_party/eurorack/rings",pathlib.Path(a.root)/"third_party/eurorack/clouds",pathlib.Path(a.root)/"third_party/stmlib"]
        sources=[]
        for base in roots:
            if base.exists():sources.extend(base.rglob("*"))
        for src in sources:
            if not src.is_file() or src.suffix not in EXT:continue
            try:lines=src.read_text(errors="replace").splitlines()
            except OSError:continue
            for i,line in enumerate(lines,1):
                if pat.search(line):f.write(f"{src}:{i}: {line.strip()}\n")
    with open("xip-strings.txt","w") as f:
        for p,elf,tab,sec in stringsets:
            items=string_rows(p,elf,tab,sec);counts=collections.Counter(x[1] for x in items)
            f.write(f"FILE {p} {sec.name} bytes={sec.data_size} strings={len(items)} unique={len(counts)}\n")
            for off,s,refs in items:f.write(f"0x{off:04x}\trefs={len(refs)}\t{';'.join(refs) or 'NO RELOCATION REFERENCE'}\t{s!r}\n")
    if sample:
        nib=[v for b in sample for v in (b&15,b>>4)]
        delta=bytes((sample[i]-sample[i-1])&255 for i in range(1,len(sample)))
        nd=bytes((nib[i]-nib[i-1])&15 for i in range(1,len(nib)))
        with open("xip-smp-data-estimates.txt","w") as f:
            f.write(f"stored_bytes={len(sample)} packed_nibbles={len(nib)}\n")
            f.write("Sample generator specifies IMA ADPCM 4-bit codes packed two per byte (8-bit storage, 4-bit sample code).\n")
            f.write(f"unique_nibbles={len(set(nib))}/16 nibble_entropy={ent(nib):.5f} bits/sample\n")
            f.write(f"byte_entropy={ent(sample):.5f} bits/byte delta_byte_entropy={ent(delta):.5f}\n")
            f.write(f"zlib9={len(zlib.compress(sample,9))} B bz2={len(bz2.compress(sample))} B lzma={len(lzma.compress(sample))} B\n")
            f.write(f"delta_zlib9={len(zlib.compress(delta,9))} B nibble_delta_entropy={ent(nd):.5f} nibble_delta_zlib={len(zlib.compress(nd,9))} B\n")
            f.write("Estimates only; no sample data or encoding changed.\n")
    print(f"Analysed {len(allrows)} retained .rodata symbols >=512 B across {len(a.objects)} supplied objects.")
if __name__=="__main__":main()
