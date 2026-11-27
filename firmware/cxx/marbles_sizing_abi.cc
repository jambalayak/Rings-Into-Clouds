// SPDX-License-Identifier: MIT
// Diagnostic-only Marbles link roots and target object storage.
// This file retains the upstream DSP call graph and object extents for memory
// measurement. None of the roots are called; no Marbles objects are constructed
// or processed, and the firmware's sequencing/audio behaviour is unchanged.
#include <stdint.h>
#include <stddef.h>

#include "marbles/random/t_generator.h"
#include "marbles/random/x_y_generator.h"
#include "marbles/random/random_stream.h"
#include "marbles/random/random_generator.h"

__attribute__((used, section(".pool"), aligned(16)))
unsigned char ric_marbles_t_generator_storage[sizeof(marbles::TGenerator)];
__attribute__((used, section(".pool"), aligned(16)))
unsigned char ric_marbles_xy_generator_storage[sizeof(marbles::XYGenerator)];
__attribute__((used, section(".pool"), aligned(16)))
unsigned char ric_marbles_random_stream_storage[sizeof(marbles::RandomStream)];
__attribute__((used, section(".pool"), aligned(16)))
unsigned char ric_marbles_random_generator_storage[sizeof(marbles::RandomGenerator)];

typedef void (marbles::TGenerator::*TInitFn)(marbles::RandomStream*, float);
typedef void (marbles::TGenerator::*TProcessFn)(
    bool, bool*, const stmlib::GateFlags*, marbles::Ramps, bool*, size_t);
typedef void (marbles::XYGenerator::*XYInitFn)(marbles::RandomStream*, float);
typedef void (marbles::XYGenerator::*XYProcessFn)(
    marbles::ClockSource, const marbles::GroupSettings&,
    const marbles::GroupSettings&, bool*, const stmlib::GateFlags*,
    const marbles::Ramps&, float*, size_t);

static void keep_t_init(void) {
    volatile TInitFn fn = &marbles::TGenerator::Init;
    (void)fn;
}
static void keep_t_process(void) {
    volatile TProcessFn fn = static_cast<TProcessFn>(&marbles::TGenerator::Process);
    (void)fn;
}
static void keep_xy_init(void) {
    volatile XYInitFn fn = &marbles::XYGenerator::Init;
    (void)fn;
}
static void keep_xy_process(void) {
    volatile XYProcessFn fn = static_cast<XYProcessFn>(&marbles::XYGenerator::Process);
    (void)fn;
}

typedef void (*MarblesRootFn)(void);
__attribute__((used, section(".rodata.ric_dsp_roots")))
static const MarblesRootFn ric_marbles_code_roots[] = {
    keep_t_init, keep_t_process, keep_xy_init, keep_xy_process
};

extern "C" uint32_t ric_marbles_size_anchor(void)
{
    uintptr_t roots = reinterpret_cast<uintptr_t>(&ric_marbles_code_roots[0]);
    uintptr_t t = reinterpret_cast<uintptr_t>(ric_marbles_t_generator_storage);
    uintptr_t xy = reinterpret_cast<uintptr_t>(ric_marbles_xy_generator_storage);
    uintptr_t stream = reinterpret_cast<uintptr_t>(ric_marbles_random_stream_storage);
    uintptr_t random = reinterpret_cast<uintptr_t>(ric_marbles_random_generator_storage);
    return static_cast<uint32_t>(roots ^ t ^ xy ^ stream ^ random ^
        sizeof(marbles::TGenerator) ^ sizeof(marbles::XYGenerator) ^
        sizeof(marbles::RandomStream) ^ sizeof(marbles::RandomGenerator));
}
