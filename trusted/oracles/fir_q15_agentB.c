/* ECS P1 oracle — Agent B (Grok Build, grok-4.5)
 * kernel: fir_q15
 * Sealed against tag prereg-v1. Authored blind: no Agent A oracle content read.
 * Spec: void fir_q15(const int16_t x[256], const int16_t h[16], int16_t y[256])
 * Q15 FIR: for each output i, acc = sum_j x[i-j]*h[j] for i-j>=0 (zero pad left),
 * then y[i] = sat_i16(acc >> 15). Saturating accumulate after the shift.
 * Pointers valid when used (option 2). No tables. Slow-and-obvious.
 */
#include <stdint.h>
#include <stddef.h>

static int16_t sat_i16(int64_t v)
{
    if (v > 32767) {
        return (int16_t)32767;
    }
    if (v < -32768) {
        return (int16_t)-32768;
    }
    return (int16_t)v;
}

void fir_q15(const int16_t x[256], const int16_t h[16], int16_t y[256])
{
    size_t i, j;

    for (i = 0; i < 256; i++) {
        int64_t acc = 0;
        for (j = 0; j < 16; j++) {
            if (i >= j) {
                acc += (int64_t)x[i - j] * (int64_t)h[j];
            }
            /* else zero-pad: contribute nothing */
        }
        y[i] = sat_i16(acc >> 15);
    }
}
