# FM-1 memory-region follow-up audit

Date: 2026-11-28
Branch: `rings-delay-packed24-exp`

## Scope

This audit checks whether unused linker regions can rescue the current packed-24 diagnostic and, separately, whether they can accommodate the approved full eight-string second Rings instance. It does not change the linker script or allocate any of the reserved regions.

## Measured diagnostic baseline

From target link run `46087345419` (commit `1a2a81a2d5274c3e9a4254fb47e3e7c7641f86ba`):

| Region / object | Measured |
|---|---:|
| POOL used | 389,920 B |
| POOL capacity | 368,640 B |
| POOL overflow | 21,280 B |
| Required POOL headroom | 8,192 B |
| Ordinary RAM used (.data + .bss) | 65,336 B |
| Ordinary RAM capacity | 73,728 B |
| Ordinary RAM free | 8,392 B |
| Required ordinary RAM headroom | 4,096 B |

The current second Rings object in this link is the reduced two-string sizing proxy (21,920 B), not the approved full eight-string instance.

## Other linker space

The linker script defines a separate 24 KiB `RAMTEXT` region. The current lean build used 3,124 B there, leaving 21,452 B. This space is reserved for code that must execute while flash is busy, so using any of it for mutable DSP data would require a deliberate `.ram_pool` section, flash-operation safety review, and updated linker/build checks. It is not automatically available to `.pool`.

The ordinary RAM region has 8,392 B free, but the build requires at least 4,096 B of headroom. At most 4,296 B could be reassigned by changing the RAM/POOL split while preserving that minimum. Such a split change would need a new linker map and must not overlap the fixed stack, NOINIT, RAMTEXT or debug reservations.

Even under the optimistic arithmetic that combines all 21,452 B of unused RAMTEXT with 4,296 B shifted from ordinary RAM, only 25,748 B could be redirected toward POOL. That remains below the 29,472 B needed merely to make the current diagnostic fit with its required 8 KiB POOL reserve. It also assumes the full RAMTEXT remainder can safely be used, which has not been established.

## Full second Rings requirement

The target size probes measured:

- reduced two-string Rings 2 proxy: 21,920 B;
- full eight-string mono Rings 2 Part: 78,152 B.

Replacing the proxy with the required full instance adds 56,232 B. With all other allocations unchanged, estimated POOL use becomes 446,152 B, or 77,512 B over the current 368,640 B capacity. To retain the required 8,192 B headroom, 85,704 B would need to be recovered or reassigned.

Even the optimistic 25,748 B combined spare-region arithmetic leaves a 59,956 B gap. This is an estimate based on target size probes and the current link; it is not a substitute for a full target link with the real second Part.

## Findings and guardrails

1. The unused RAMTEXT region is not a hidden 21 KiB pool; it has a flash-execution responsibility and needs a dedicated, validated data-placement design.
2. Reassigning the entire measured spare RAMTEXT plus all ordinary-RAM capacity above its minimum still cannot accommodate the full eight-string second Rings instance.
3. The existing compact Clouds buffer layout in this branch remains experimental. This audit does not endorse it as the product's normal Clouds configuration.
4. Do not reduce Clouds recording/workspace buffers, remove Rings models, reduce the eight-string bank, share state between Rings instances, or silently remove other user-approved features to make the link pass.
5. Do not label the current C ABI diagnostic as playable: `firmware/src/main.c` only calls the link-retention anchor. The Rings and Clouds processors are not constructed or called by the live audio path.

## Next viable decision

A full two-instance implementation with all approved buffers and headroom needs a materially different memory budget or hardware memory resource. The current linker map exposes no such resource. Before further implementation, the remaining options are explicit product-level trade-offs (for example, a separate reduced-resource performance profile) or confirmation of a hardware revision with additional writable memory. No trade-off is selected here.
