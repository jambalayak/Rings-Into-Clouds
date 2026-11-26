/* SPDX-License-Identifier: GPL-3.0-only
 * RINGS INTO CLOUDS C ABI.
 *
 * This translation unit reserves one full six-model Rings instance and one stock
 * stereo Clouds instance. The boot anchor retains the objects, buffers and
 * processing entry points, but never constructs or runs the DSP. */
#include <stdint.h>
#include <stddef.h>
#include <new>

#include "rings_clouds_abi.h"
#include "rings/dsp/part.h"
#include "rings/dsp/strummer.h"
#include "rings/dsp/performance_state.h"
#include "rings/dsp/patch.h"
#include "clouds/dsp/granular_processor.h"
#include "clouds/dsp/frame.h"

extern "C" {
__attribute__((used, section(".pool"), aligned(16)))
unsigned char ric_rings_part_storage[sizeof(rings::Part)];
__attribute__((used, section(".pool"), aligned(16)))
unsigned char ric_rings_strummer_storage[sizeof(rings::Strummer)];
__attribute__((used, section(".pool"), aligned(16)))
unsigned char ric_rings_reverb_buffer[65536];
__attribute__((used, section(".pool"), aligned(16)))
unsigned char ric_clouds_processor_storage[sizeof(clouds::GranularProcessor)];

/* Stock stereo layout: 118,784 B large buffer (sample + workspace) in POOL,
 * 65,408 B small buffer in ordinary RAM. The buffers are deliberately full
 * sized at this measurement gate; no shortened recording profile is assumed. */
__attribute__((used, section(".pool"), aligned(16)))
unsigned char ric_clouds_large_buffer[118784];
__attribute__((used, section(".bss.ric_clouds_small"), aligned(16)))
unsigned char ric_clouds_small_buffer[65408];
}

static uint8_t ric_dsp_constructed;

static rings::Part *rings_part()
{
    return reinterpret_cast<rings::Part *>(ric_rings_part_storage);
}

static rings::Strummer *rings_strummer()
{
    return reinterpret_cast<rings::Strummer *>(ric_rings_strummer_storage);
}

static clouds::GranularProcessor *clouds_processor()
{
    return reinterpret_cast<clouds::GranularProcessor *>(ric_clouds_processor_storage);
}

extern "C" int32_t ric_dsp_construct(void)
{
    if (!ric_dsp_constructed) {
        new (ric_rings_part_storage) rings::Part();
        new (ric_rings_strummer_storage) rings::Strummer();
        new (ric_clouds_processor_storage) clouds::GranularProcessor();
        ric_dsp_constructed = 1;
    }
    return 0;
}

extern "C" int32_t ric_dsp_init(uint32_t sample_rate_hz, uint32_t inter_onset_us)
{
    if (ric_dsp_construct() != 0 || !sample_rate_hz)
        return -1;
    rings_part()->Init(reinterpret_cast<uint16_t *>(ric_rings_reverb_buffer));
    rings_strummer()->Init(static_cast<float>(inter_onset_us) * 0.000001f,
                           static_cast<float>(sample_rate_hz));
    clouds_processor()->Init(ric_clouds_large_buffer, sizeof ric_clouds_large_buffer,
                             ric_clouds_small_buffer, sizeof ric_clouds_small_buffer);
    return 0;
}

extern "C" void ric_rings_strummer_process(const float *exciter, uint32_t frames,
                                             void *performance_state)
{
    if (!ric_dsp_constructed || !performance_state || frames > rings::kMaxBlockSize)
        return;
    rings_strummer()->Process(exciter, frames,
        static_cast<rings::PerformanceState *>(performance_state));
}

extern "C" void ric_rings_process(const void *performance_state, const void *patch,
                                  const float *input, float *out, float *aux, uint32_t frames)
{
    if (!ric_dsp_constructed || !performance_state || !patch ||
        !out || !aux || frames > rings::kMaxBlockSize)
        return;
    rings_part()->Process(*static_cast<const rings::PerformanceState *>(performance_state),
                          *static_cast<const rings::Patch *>(patch),
                          input, out, aux, frames);
}

extern "C" void ric_clouds_prepare(void)
{
    if (ric_dsp_constructed)
        clouds_processor()->Prepare();
}

extern "C" void ric_clouds_process(int16_t *input_interleaved,
                                    int16_t *output_interleaved, uint32_t frames)
{
    if (!ric_dsp_constructed || !input_interleaved || !output_interleaved ||
        frames > clouds::kMaxBlockSize)
        return;
    clouds_processor()->Process(
        reinterpret_cast<clouds::ShortFrame *>(input_interleaved),
        reinterpret_cast<clouds::ShortFrame *>(output_interleaved), frames);
}

extern "C" uint32_t ric_dsp_abi_version(void)
{
    return 0x00010000u;
}

extern "C" void ric_dsp_get_sizes(ric_dsp_sizes_t *sizes)
{
    if (!sizes)
        return;
    sizes->rings_part_bytes = sizeof(rings::Part);
    sizes->rings_strummer_bytes = sizeof(rings::Strummer);
    sizes->clouds_processor_bytes = sizeof(clouds::GranularProcessor);
    sizes->clouds_large_buffer_bytes = sizeof ric_clouds_large_buffer;
    sizes->clouds_small_buffer_bytes = sizeof ric_clouds_small_buffer;
}

/* Keep all exported entry points live if section garbage collection is enabled
 * by a later linker change. The C boot call reads this table through the anchor. */
typedef void (*ric_root_fn)(void);
static ric_root_fn const volatile ric_dsp_code_roots[]
    __attribute__((used, section(".rodata.ric_dsp_roots"))) = {
        reinterpret_cast<ric_root_fn>(&ric_dsp_construct),
        reinterpret_cast<ric_root_fn>(&ric_dsp_init),
        reinterpret_cast<ric_root_fn>(&ric_rings_strummer_process),
        reinterpret_cast<ric_root_fn>(&ric_rings_process),
        reinterpret_cast<ric_root_fn>(&ric_clouds_prepare),
        reinterpret_cast<ric_root_fn>(&ric_clouds_process),
        reinterpret_cast<ric_root_fn>(&ric_dsp_get_sizes)
    };

extern "C" uint32_t ric_dsp_link_anchor(void)
{
    uintptr_t roots = reinterpret_cast<uintptr_t>(&ric_dsp_code_roots[0]);
    uintptr_t part = reinterpret_cast<uintptr_t>(ric_rings_part_storage);
    uintptr_t strummer = reinterpret_cast<uintptr_t>(ric_rings_strummer_storage);
    uintptr_t reverb = reinterpret_cast<uintptr_t>(ric_rings_reverb_buffer);
    uintptr_t processor = reinterpret_cast<uintptr_t>(ric_clouds_processor_storage);
    uintptr_t large = reinterpret_cast<uintptr_t>(ric_clouds_large_buffer);
    uintptr_t small = reinterpret_cast<uintptr_t>(ric_clouds_small_buffer);
    return static_cast<uint32_t>(roots ^ part ^ strummer ^ reverb ^ processor ^ large ^ small ^
        sizeof(rings::Part) ^ sizeof(rings::Strummer) ^ sizeof(clouds::GranularProcessor));
}
