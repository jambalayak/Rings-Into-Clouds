/* Compile-time only: measure a one-voice Rings Part beside the primary four-voice Part. */
#include "rings/dsp/part.h"
#include "rings_mono/dsp/part.h"

extern "C" {
__attribute__((used))
unsigned char ric_marbles2_size_rings_mono_part[sizeof(rings_mono::Part)];
}
