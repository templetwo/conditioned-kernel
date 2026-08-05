/* ECS P1 oracle — Agent A (Claude Code, Opus 5).
 * kernel: matmul8_i32
 * Sealed against tag prereg-v1 under hash-and-seal (SPEC §6 amendment,
 * PREREG §8). Authored blind: no Agent B matmul8_i32 seal existed on the
 * board at authorship (verified by query, not assumed) and no Agent B
 * content was read. Written from the SPEC §5 row only.
 *
 * SPEC §5: void matmul8_i32(const int32_t a[64], const int32_t b[64], int32_t c[64])
 *          domain "entries in [-1024, 1023]"
 *          note  "domain bound keeps products in range, no UB ambiguity"
 *
 * WHAT THE SPEC PINS. The domain bound is doing real work here and the note
 * says so. Each product is at most 1024*1024 = 2^20 in magnitude; a row-column
 * dot product sums eight of them, reaching at most 2^23. That is comfortably
 * inside int32, so unlike fir_q15 there is NO accumulator-width ambiguity and
 * no overflow to reason about. This kernel is deliberately closed where
 * fir_q15 was open.
 *
 * WHAT THE SPEC DOES NOT PIN — one bit, and it is the whole kernel:
 *
 *   [M1] MEMORY LAYOUT. The signature gives three flat 64-element arrays and
 *        never states that they are 8x8, nor in which order. "matmul8" plus
 *        64 elements makes 8x8 overwhelmingly the intended reading, but
 *        ROW-MAJOR versus COLUMN-MAJOR is genuinely unstated.
 *        Chosen: ROW-MAJOR throughout, for a, b and c alike.
 *          c[i*8 + j] = sum over k of a[i*8 + k] * b[k*8 + j]
 *        Rationale: row-major is C's own array convention — int32_t m[8][8]
 *        laid out flat is row-major — so a C signature taking a flat array
 *        most naturally denotes it. Column-major would be a deliberate
 *        departure and the spec signals none.
 *        NOTE: this choice is not symmetric. Reading all three operands as
 *        column-major yields the transpose of this result, not the same
 *        matrix, so a seat choosing the other convention will disagree on
 *        every non-symmetric input. This is a single unpinned bit with a
 *        large behavioural consequence, which makes it a cleaner test of
 *        LN-2A than fir_q15's four small ones.
 *
 * Slow-and-obvious per SPEC §6: the textbook triple loop, no blocking, no
 * transposition, no accumulation tricks.
 */
#include <stdint.h>
#include <stddef.h>

#define MM_DIM 8

void matmul8_i32(const int32_t a[64], const int32_t b[64], int32_t c[64])
{
    for (int i = 0; i < MM_DIM; i++) {
        for (int j = 0; j < MM_DIM; j++) {
            int32_t acc = 0;                  /* domain bound keeps this in range */

            for (int k = 0; k < MM_DIM; k++) {
                acc += a[i * MM_DIM + k] * b[k * MM_DIM + j];   /* [M1] row-major */
            }

            c[i * MM_DIM + j] = acc;
        }
    }
}
