#pragma once
#include <stdint.h>
#include <stddef.h>
#include <math.h>
#include <algorithm>

namespace rings {
extern uint64_t q24_saturation_count;
extern float q24_max_abs;

/* Test-only packed signed-24 delay storage. DSP arithmetic and interpolation
 * remain float; only the backing samples are quantised. */
template <size_t N>
class Q24DelayLine {
 public:
  Q24DelayLine() : write_ptr_(0), delay_(1) {}
  void Init() { Reset(); }
  void Reset() {
    for (size_t i = 0; i < N * 3; ++i) line_[i] = 0;
    write_ptr_ = 0;
    delay_ = 1;
  }
  inline void set_delay(size_t delay) { delay_ = delay; }
  inline void Write(float sample) {
    const float a = fabsf(sample);
    if (a > q24_max_abs) q24_max_abs = a;
    long q = lrintf(sample * kScale);
    if (q > 8388607L) { q = 8388607L; ++q24_saturation_count; }
    if (q < -8388608L) { q = -8388608L; ++q24_saturation_count; }
    Store(write_ptr_, static_cast<int32_t>(q));
    write_ptr_ = (write_ptr_ + N - 1) % N;
  }
  inline float Read() const { return Decode(Load((write_ptr_ + delay_) % N)); }
  inline float Read(size_t delay) const { return Decode(Load((write_ptr_ + delay) % N)); }
  inline float Read(float delay) const {
    if (delay < 0.0f) delay = 0.0f;
    size_t i = static_cast<size_t>(delay);
    float f = delay - static_cast<float>(i);
    float a = Read(i), b = Read(i + 1);
    return a + (b - a) * f;
  }
  inline float ReadHermite(float delay) const {
    if (delay < 0.0f) delay = 0.0f;
    size_t i = static_cast<size_t>(delay);
    float f = delay - static_cast<float>(i);
    const float xm1 = Read((i + N - 1) % N);
    const float x0 = Read(i);
    const float x1 = Read(i + 1);
    const float x2 = Read(i + 2);
    const float c = (x1 - xm1) * 0.5f;
    const float v = x0 - x1;
    const float w = c + v;
    const float a = w + v + (x2 - x0) * 0.5f;
    const float b_neg = w + a;
    return (((a * f) - b_neg) * f + c) * f + x0;
  }
  inline float Allpass(float input, size_t delay, float coefficient) {
    const float read = Read(delay);
    const float value = input + coefficient * read;
    Write(value);
    return -value * coefficient + read;
  }
  inline float WriteRead(float sample, float delay) {
    Write(sample);
    return Read(delay);
  }
 private:
  static constexpr float kScale = 2097152.0f;  // Q3.21, range [-4, 4).
  inline void Store(size_t index, int32_t value) {
    const uint32_t bits = static_cast<uint32_t>(value);
    const size_t p = index * 3;
    line_[p] = static_cast<uint8_t>(bits);
    line_[p + 1] = static_cast<uint8_t>(bits >> 8);
    line_[p + 2] = static_cast<uint8_t>(bits >> 16);
  }
  inline int32_t Load(size_t index) const {
    const size_t p = index * 3;
    uint32_t bits = static_cast<uint32_t>(line_[p]) |
                    (static_cast<uint32_t>(line_[p + 1]) << 8) |
                    (static_cast<uint32_t>(line_[p + 2]) << 16);
    if (bits & 0x800000u) bits |= 0xff000000u;
    return static_cast<int32_t>(bits);
  }
  static inline float Decode(int32_t value) {
    return static_cast<float>(value) * (1.0f / kScale);
  }
  size_t write_ptr_;
  size_t delay_;
  uint8_t line_[N * 3];
};
}  // namespace rings
