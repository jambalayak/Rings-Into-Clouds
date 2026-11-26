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
static const int kNotes[4] = {36, 48, 60, 72};
struct Profile { const char *name; float structure, brightness, damping, position, seconds; };
static const Profile kProfiles[] = {
  {"neutral", 0.50f, 0.50f, 0.50f, 0.50f, 8.0f},
  {"bright", 0.86f, 0.96f, 0.30f, 0.90f, 8.0f},
  {"long_decay", 0.55f, 0.78f, 0.995f, 0.55f, 12.0f}
};
static const uint64_t kStrumFrames[4] = {0, 11029, 22058, 33087};

int main(int argc, char **argv) {
  if (argc != 2) return 2;
  FILE *audio = fopen(argv[1], "wb");
  FILE *meta = fopen("segments.csv", "w");
  if (!audio || !meta) return 3;
  fprintf(meta, "start,frames,model,profile,saturation_count,max_abs_delay_value,polyphony,strums\n");
  uint64_t cursor = 0, total_sat = 0;
  float global_max = 0.0f;
  for (int model = 0; model < 5; ++model) {
    for (size_t pi = 0; pi < sizeof(kProfiles)/sizeof(kProfiles[0]); ++pi) {
      const Profile &p = kProfiles[pi];
      rings::qn_saturation_count = 0;
      rings::qn_max_abs = 0.0f;
      rings::Part part;
      part.Init();
      part.set_model(static_cast<rings::ResonatorModel>(model));
      part.set_polyphony(4);
      rings::Patch patch = {p.structure, p.brightness, p.damping, p.position};
      rings::PerformanceState ps = {};
      ps.internal_exciter = true;
      ps.internal_strum = true;
      ps.internal_note = true;
      ps.tonic = 0.0f;
      ps.fm = 0.0f;
      ps.chord = 0;
      stmlib::Random::Seed(0x71A7C0DEu + model * 101u + pi * 17u);
      const uint64_t frames = static_cast<uint64_t>(p.seconds * kRate);
      const uint64_t start = cursor;
      size_t next_strum = 0;
      for (uint64_t offset = 0; offset < frames; offset += kBlock) {
        float in[kBlock] = {}, out[kBlock] = {}, aux[kBlock] = {};
        const size_t n = static_cast<size_t>(std::min<uint64_t>(kBlock, frames-offset));
        ps.strum = false;
        if (next_strum < 4 && offset >= kStrumFrames[next_strum]) {
          ps.note = static_cast<float>(kNotes[next_strum]);
          ps.strum = true;
          ++next_strum;
        }
        part.Process(ps, patch, in, out, aux, n);
        for (size_t i=0; i<n; ++i) {
          float pair[2] = {out[i], aux[i]};
          if (fwrite(pair, sizeof(float), 2, audio) != 2) return 4;
        }
      }
      fprintf(meta, "%llu,%llu,%d,%s,%llu,%.9g,4,%u\n",
        static_cast<unsigned long long>(start), static_cast<unsigned long long>(frames),
        model, p.name, static_cast<unsigned long long>(rings::qn_saturation_count),
        rings::qn_max_abs, static_cast<unsigned>(next_strum));
      total_sat += rings::qn_saturation_count;
      global_max = std::max(global_max, rings::qn_max_abs);
      cursor += frames;
    }
  }
  fclose(audio); fclose(meta);
  FILE *stats = fopen("delay_stats.txt", "w");
  if (!stats) return 5;
  fprintf(stats, "part_size_bytes=%zu\nstring_size_bytes=%zu\nqn_saturation_count=%llu\nqn_max_abs=%.9g\n",
    sizeof(rings::Part), sizeof(rings::String),
    static_cast<unsigned long long>(total_sat), global_max);
  fclose(stats);
  return 0;
}
