#pragma once
#include <stdint.h>
#include <stddef.h>
#include <math.h>
#include <algorithm>
#include <cmath>

#ifndef RINGS_DELAY_SCALE
#define RINGS_DELAY_SCALE 16384
#endif

namespace rings {
extern uint64_t qn_saturation_count;
extern float qn_max_abs;

/* Test-only signed 16-bit delay storage. RINGS_DELAY_SCALE selects the
 * quantizer gain, allowing range/precision trade-offs without changing DSP.
 * All other Rings DSP calculations remain float. */
template <size_t N>
class QNDelayLine {
 public:
  QNDelayLine() : write_ptr_(0), delay_(1) {}
  void Init() { Reset(); }
  void Reset() {
    std::fill(line_, line_ + N, int16_t(0));
    write_ptr_ = 0;
    delay_ = 1;
  }
  inline void set_delay(size_t delay) { delay_ = delay; }
  inline void Write(float sample) {
    const float a = fabsf(sample);
    if (a > qn_max_abs) qn_max_abs = a;
    long q = lrintf(sample * kScale);
    if (q > 32767) { q = 32767; ++qn_saturation_count; }
    if (q < -32768) { q = -32768; ++qn_saturation_count; }
    line_[write_ptr_] = static_cast<int16_t>(q);
    write_ptr_ = (write_ptr_ + N - 1) % N;
  }
  inline float Read() const { return sample((write_ptr_ + delay_) % N); }
  inline float Read(size_t delay) const { return sample((write_ptr_ + delay) % N); }
  inline float Read(float delay) const {
    if (delay < 0.0f) delay = 0.0f;
    size_t i = static_cast<size_t>(delay);
    float f = delay - static_cast<float>(i);
    float a = sample((write_ptr_ + i) % N);
    float b = sample((write_ptr_ + i + 1) % N);
    return a + (b - a) * f;
  }
  inline float ReadHermite(float delay) const {
    if (delay < 0.0f) delay = 0.0f;
    size_t i = static_cast<size_t>(delay);
    float f = delay - static_cast<float>(i);
    const float xm1 = sample((write_ptr_ + i + N - 1) % N);
    const float x0  = sample((write_ptr_ + i) % N);
    const float x1  = sample((write_ptr_ + i + 1) % N);
    const float x2  = sample((write_ptr_ + i + 2) % N);
    const float c = (x1 - xm1) * 0.5f;
    const float v = x0 - x1;
    const float w = c + v;
    const float a = w + v + (x2 - x0) * 0.5f;
    const float b_neg = w + a;
    return (((a * f) - b_neg) * f + c) * f + x0;
  }
  inline float Allpass(float input, size_t delay, float coefficient) {
    const float read = sample((write_ptr_ + delay) % N);
    const float value = input + coefficient * read;
    Write(value);
    const float stored = sample((write_ptr_ + 1) % N);
    return -stored * coefficient + read;
  }
 private:
  static constexpr float kScale = static_cast<float>(RINGS_DELAY_SCALE);
  inline float sample(size_t i) const {
    return static_cast<float>(line_[i]) / kScale;
  }
  size_t write_ptr_;
  size_t delay_;
  int16_t line_[N];
};
}  // namespace rings
