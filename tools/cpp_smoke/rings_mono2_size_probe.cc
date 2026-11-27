/* Compile-time only: measure a one-voice, two-string-bank Rings Part.
 * Diagnostic only; this does not alter runtime firmware or sound.
 */
#include "rings/dsp/part.h"
#include "rings_mono2/dsp/part.h"

extern "C" {
__attribute__((used))
unsigned char ric_marbles2_size_rings_mono2_part[sizeof(rings_mono2::Part)];
}
