// SPDX-License-Identifier: GPL-3.0-only
// Compile-time target sizeof measurements only; no objects are constructed.
#include "rings/dsp/part.h"
#include "rings/dsp/string.h"
#include "rings/dsp/strummer.h"
#include "clouds/dsp/granular_processor.h"

static_assert(rings::RESONATOR_MODEL_LAST == 5, "RINGS INTO CLOUDS exposes exactly five original Rings models");

extern "C" {
__attribute__((used)) unsigned char ric_size_rings_part[sizeof(rings::Part)];
__attribute__((used)) unsigned char ric_size_rings_string[sizeof(rings::String)];
__attribute__((used)) unsigned char ric_size_rings_strummer[sizeof(rings::Strummer)];
__attribute__((used)) unsigned char ric_size_clouds_processor[sizeof(clouds::GranularProcessor)];
}
