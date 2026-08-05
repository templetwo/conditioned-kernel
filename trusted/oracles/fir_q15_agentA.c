/* ECS P1 oracle — Agent A (Claude Code, Opus 5).
 * kernel: fir_q15
 * Sealed against tag prereg-v1 under hash-and-seal (SPEC §6 amendment,
 * PREREG §8). Authored blind: Agent B's fir_q15 seal hash was on the board
 * (#13909) but its content was NOT read. Written from the SPEC §5 row only.
 *
 * SPEC §5: void fir_q15(const int16_t x[256], const int16_t h[16], int16_t y[256])
 *          domain "Q15, saturating accumulate >>15".
 *
 * THE SPEC ROW IS UNDERSPECIFIED IN FOUR PLACES. Each choice below is a
 * reading, not a derivation, and is named here so that a divergence from the
 * other seat is attributable to a specific unpinned bit rather than to a bug.
 * These are exactly the "unpinned specification bits" D exists to count.
 *
 *   [A1] BOUNDARY. y has 256 elements, so every output must be defined,
 *        including y[0..14] where the filter reaches back past x[0].
 *        Chosen: ZERO-PAD, x[i] = 0 for i < 0. The alternative (define only
 *        y[15..255]) contradicts the declared output length.
 *
 *   [A2] ACCUMULATOR WIDTH. Sixteen products of two int16 values reach
 *        16 * 2^30 = 2^34, which OVERFLOWS int32. An int32 accumulator is
 *        therefore not merely a style choice, it is undefined behaviour on
 *        the domain's extremes.
 *        Chosen: int64_t accumulator. Exact, no intermediate saturation.
 *
 *   [A3] WHERE SATURATION APPLIES. "saturating accumulate >>15" can be read
 *        as saturating the accumulator, or as saturating the final result.
 *        Chosen: accumulate exactly, shift, then saturate the RESULT to the
 *        int16 range. This is the standard Q15 pipeline: Q15 x Q15 -> Q30,
 *        sum stays Q30-with-headroom, >>15 returns to Q15, and the Q15
 *        output must fit int16.
 *
 *   [A4] ROUNDING. ">>15" is taken literally as an arithmetic right shift
 *        (truncation toward negative infinity), not round-to-nearest. On
 *        gcc/aarch64 and gcc/x86-64 right shift of a negative signed value
 *        is documented arithmetic; the spec's literal ">>15" is followed
 *        rather than substituting a rounding convention it does not state.
 *
 * Slow-and-obvious per SPEC §6: direct double loop, no reordering, no
 * accumulator tricks, no table.
 */
#include <stdint.h>
#include <stddef.h>

#define FIR_N    256
#define FIR_TAPS 16

void fir_q15(const int16_t x[256], const int16_t h[16], int16_t y[256])
{
    for (int n = 0; n < FIR_N; n++) {
        int64_t acc = 0;                      /* [A2] exact, cannot overflow */

        for (int k = 0; k < FIR_TAPS; k++) {
            const int idx = n - k;
            const int64_t xv = (idx >= 0) ? (int64_t)x[idx] : 0;   /* [A1] */
            acc += xv * (int64_t)h[k];
        }

        const int64_t shifted = acc >> 15;    /* [A4] arithmetic, truncating */

        /* [A3] saturate the result into Q15 / int16 */
        int64_t sat = shifted;
        if (sat >  32767) sat =  32767;
        if (sat < -32768) sat = -32768;

        y[n] = (int16_t)sat;
    }
}
