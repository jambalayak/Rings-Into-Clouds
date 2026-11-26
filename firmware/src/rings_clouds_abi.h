/* SPDX-License-Identifier: GPL-3.0-only
 * RINGS INTO CLOUDS: stable C boundary for the pinned Mutable Instruments DSP.
 * DSP types remain private to the C++ implementation. No audio route is attached here. */
#ifndef RIC_RINGS_CLOUDS_ABI_H
#define RIC_RINGS_CLOUDS_ABI_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint32_t rings_part_bytes;
    uint32_t rings_strummer_bytes;
    uint32_t clouds_processor_bytes;
    uint32_t clouds_large_buffer_bytes;
    uint32_t clouds_small_buffer_bytes;
} ric_dsp_sizes_t;

/* Called by the firmware boot path only to root the linked DSP code and storage.
 * It does not construct, initialise, prepare or process either processor. */
uint32_t ric_dsp_link_anchor(void);
uint32_t ric_dsp_abi_version(void);
void ric_dsp_get_sizes(ric_dsp_sizes_t *sizes);

/* Explicit lifecycle and processing entry points for the later audio-integration gate.
 * These are deliberately not called by the current firmware audio path. */
int32_t ric_dsp_construct(void);
int32_t ric_dsp_init(uint32_t sample_rate_hz, uint32_t inter_onset_us);
void ric_rings_strummer_process(const float *exciter, uint32_t frames, void *performance_state);
void ric_rings_process(const void *performance_state, const void *patch,
                       const float *input, float *out, float *aux, uint32_t frames);
void ric_clouds_prepare(void);
void ric_clouds_process(int16_t *input_interleaved, int16_t *output_interleaved, uint32_t frames);

#ifdef __cplusplus
}
#endif
#endif
