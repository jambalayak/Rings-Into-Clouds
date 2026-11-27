#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Compile-only UI function-size probes. Outputs reports; never links or runs firmware."""
import os, pathlib, re, subprocess

root=pathlib.Path(__file__).resolve().parents[1]
tc=pathlib.Path(os.environ["JIELI_TOOLCHAIN"])
bin=tc/"pi32v2/bin"; common=tc/"common/bin"
clang=bin/"clang"; objdump=common/"objdump"
out=root/"build/xip-function-probes"; out.mkdir(parents=True,exist_ok=True)
hal=[root/"firmware/hal",root/"firmware/bsp/chip",root/"firmware/bsp/boards/fm1"]
flags=["-target","pi32v2","-mcpu=r3","-mfprev1","-Oz","-ffunction-sections","-fno-builtin",
       "-Wall","-Wno-unused-function","-I"+str(root/"firmware/src"),
       "-I"+str(root/"build/gen"),*["-I"+str(x) for x in hal],
       '-DFELUCCA_ID="FM-1_900"','-DFELUCCA_RIC=1']
probes={
 "baseline":[],
 "no-inline-functions":["-fno-inline-functions"],
 "no-unroll-loops":["-fno-unroll-loops"],
 "no-jump-tables":["-fno-jump-tables"],
 "reduced-inline-threshold":["-mllvm","-inline-threshold=10"],
}
rows=[]
for name,extra in probes.items():
    obj=out/(name+".o")
    cmd=[str(clang),*flags,*extra,"-c",str(root/"firmware/src/felucca.c"),"-o",str(obj)]
    r=subprocess.run(cmd,cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (out/(name+".compile.log")).write_text(r.stdout)
    if r.returncode:
        rows.append(f"{name}: COMPILE FAILED exit={r.returncode}")
        continue
    syms=subprocess.run([str(objdump),"-t",str(obj)],text=True,capture_output=True)
    sizes={}
    for line in syms.stdout.splitlines():
        fields=line.split()
        if len(fields)>=5 and fields[-1] in ("ui_input","draw_graph"):
            for token in reversed(fields[:-1]):
                if re.fullmatch(r"[0-9a-fA-F]+",token):
                    sizes[fields[-1]]=int(token,16);break
    hdr=subprocess.run([str(objdump),"-h",str(obj)],text=True,capture_output=True)
    text_bytes=0
    for line in hdr.stdout.splitlines():
        fields=line.split()
        if len(fields)>=3 and fields[1].startswith(".text"):
            try:text_bytes+=int(fields[2],16)
            except ValueError:pass
    rows.append(f"{name}: object={obj.stat().st_size} B .text={text_bytes} B ui_input={sizes.get('ui_input','MISSING')} B draw_graph={sizes.get('draw_graph','MISSING')} B")
(out/"probe-sizes.txt").write_text("\n".join(rows)+"\n")
print("\n".join(rows))
print("Compile-only probes; no firmware link, no runtime test, no flags adopted.")
