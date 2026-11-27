// SPDX-License-Identifier: MIT
// Compile-time sizeof measurements for the upstream Mutable Instruments Marbles DSP.
// This does not construct, initialize, or process any sequencer objects.
#include "marbles/random/t_generator.h"
#include "marbles/random/x_y_generator.h"
#include "marbles/random/output_channel.h"
#include "marbles/random/random_sequence.h"
#include "marbles/random/random_stream.h"
#include "marbles/random/random_generator.h"

extern "C" {
__attribute__((used)) unsigned char ric_marbles_size_t_generator[sizeof(marbles::TGenerator)];
__attribute__((used)) unsigned char ric_marbles_size_xy_generator[sizeof(marbles::XYGenerator)];
__attribute__((used)) unsigned char ric_marbles_size_output_channel[sizeof(marbles::OutputChannel)];
__attribute__((used)) unsigned char ric_marbles_size_random_sequence[sizeof(marbles::RandomSequence)];
__attribute__((used)) unsigned char ric_marbles_size_random_stream[sizeof(marbles::RandomStream)];
__attribute__((used)) unsigned char ric_marbles_size_random_generator[sizeof(marbles::RandomGenerator)];
}
