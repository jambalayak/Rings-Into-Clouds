#include <stdint.h>
#include <algorithm>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "rings/dsp/part.h"
#include "rings/dsp/performance_state.h"
#include "rings/dsp/patch.h"
#include "stmlib/utils/random.h"

namespace rings {
uint64_t qn_saturation_count = 0;
float qn_max_abs = 0.0f;
}

static const float kRate = 24000000.0f / 544.0f;
static const size_t kBlock = rings::kMaxBlockSize;
static const int kNotes[4] = {36, 48, 60, 84};

struct Profile {
  const char *name;
  float structure, brightness, damping, position;
  float seconds;
  bool external_exciter;
  float external_amplitude;
  uint64_t note_interval_frames;
};

static const Profile kProfiles[] = {
  {"neutral", 0.50f, 0.50f, 0.50f, 0.50f, 4.0f, false, 0.0f, 11029},
  {"bright", 0.86f, 0.96f, 0.30f, 0.90f, 4.0f, false, 0.0f, 11029},
  {"high_resonance", 0.72f, 0.84f, 0.9995f, 0.55f, 8.0f, false, 0.0f, 11029},
  {"loud_external", 0.70f, 0.92f, 0.55f, 0.45f, 4.0f, true, 1.75f, 11029},
  {"rapid_note_change", 0.78f, 0.88f, 0.90f, 0.20f, 4.0f, false, 0.0f, 2206}
};

int main(int argc, char **argv) {
  if (argc != 2) return 2;
  FILE *audio = fopen(argv[1], "wb");
  FILE *meta = fopen("segments.csv", "w");
  if (!audio || !meta) return 3;
  fprintf(meta, "start,frames,model,profile,damping,external_peak,saturation_count,max_abs_delay_value,polyphony,strums\n");
  uint64_t cursor = 0;

  for (int model = 0; model < 5; ++model) {
    for (size_t pi = 0; pi < sizeof(kProfiles) / sizeof(kProfiles[0]); ++pi) {
      const Profile &p = kProfiles[pi];
      rings::qn_saturation_count = 0;
      rings::qn_max_abs = 0.0f;
      rings::Part part;
      part.Init();
      part.set_model(static_cast<rings::ResonatorModel>(model));
      part.set_polyphony(4);
      rings::Patch patch = {p.structure, p.brightness, p.damping, p.position};
      rings::PerformanceState ps = {};
      ps.internal_exciter = !p.external_exciter;
      ps.internal_strum = true;
      ps.internal_note = true;
      ps.tonic = 0.0f;
      ps.note = static_cast<float>(kNotes[0]);
      ps.fm = 0.0f;
      ps.chord = 0;
      stmlib::Random::Seed(0x71A7C0DEu + model * 101u + static_cast<unsigned>(pi) * 17u);

      const uint64_t frames = static_cast<uint64_t>(p.seconds * kRate);
      const uint64_t start = cursor;
      size_t next_note = 0;
      for (uint64_t offset = 0; offset < frames; offset += kBlock) {
        float in[kBlock] = {}, out[kBlock] = {}, aux[kBlock] = {};
        const size_t n = static_cast<size_t>(std::min<uint64_t>(kBlock, frames - offset));
        if (p.external_exciter) {
          for (size_t i = 0; i < n; ++i) {
            const double t = static_cast<double>(cursor + offset + i) / kRate;
            in[i] = p.external_amplitude * sinf(static_cast<float>(2.0 * 3.14159265358979323846 * 173.0 * t));
          }
        }
        ps.strum = false;
        if (next_note < 4 && offset >= p.note_interval_frames * next_note) {
          ps.note = static_cast<float>(kNotes[next_note]);
          ps.strum = true;
          ++next_note;
        }
        part.Process(ps, patch, in, out, aux, n);
        for (size_t i = 0; i < n; ++i) {
          const float pair[2] = {out[i], aux[i]};
          if (fwrite(pair, sizeof(float), 2, audio) != 2) return 4;
        }
      }
      fprintf(meta, "%llu,%llu,%d,%s,%.7f,%.4f,%llu,%.9g,4,%u\n",
        static_cast<unsigned long long>(start),
        static_cast<unsigned long long>(frames), model, p.name,
        p.damping, p.external_amplitude,
        static_cast<unsigned long long>(rings::qn_saturation_count),
        rings::qn_max_abs, static_cast<unsigned>(next_note));
      cursor += frames;
    }
  }
  fclose(audio);
  fclose(meta);
  FILE *stats = fopen("delay_stats.txt", "w");
  if (!stats) return 5;
  fprintf(stats, "part_size_bytes=%zu\nstring_size_bytes=%zu\nqn_saturation_count=%llu\nqn_max_abs=%.9g\n",
    sizeof(rings::Part), sizeof(rings::String),
    static_cast<unsigned long long>(rings::qn_saturation_count), rings::qn_max_abs);
  fclose(stats);
  return 0;
}
