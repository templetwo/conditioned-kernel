/* ECS P1 oracle — Agent A (Claude Code, Opus 5).
 * kernel: median3x3_u8
 * Sealed against tag prereg-v1 under hash-and-seal (SPEC §6 amendment,
 * PREREG §8). Authored blind: no Agent B median3x3_u8 seal existed on the
 * board at authorship (verified by query, not assumed) and no Agent B
 * content was read. Written from the SPEC §5 row only.
 *
 * SPEC §5: void median3x3_u8(const uint8_t in[16*16], uint8_t out[14*14])
 *          domain "interior only"
 *          note  "perf-interesting, sorting-network friendly"
 *
 * WHAT THE SPEC PINS, via the array sizes. A 16x16 input and a 14x14 output
 * fixes the boundary policy arithmetic-free: 16 - 14 = 2, one pixel of margin
 * on each side. "interior only" then means exactly that no output is produced
 * for the border, so no padding, replication or reflection is needed or
 * permitted. This is the boundary question that fir_q15 left open [A1],
 * answered here by the declared shapes rather than by convention. Good spec.
 *
 * WHAT THE SPEC DOES NOT PIN:
 *
 *   [D1] MEMORY LAYOUT. Flat arrays again, with no statement that they are
 *        16x16 and 14x14, nor in which order.
 *        Chosen: ROW-MAJOR for both, matching C's own flat-array layout and
 *        my matmul8_i32 reading. in[r*16 + c], out[(r-1)*14 + (c-1)].
 *        Unlike matmul8_i32 the penalty for guessing wrong is smaller here:
 *        a transposed reading still produces the median of a 3x3 neighbourhood,
 *        just of the transposed image, so results coincide on any symmetric
 *        input and diverge otherwise.
 *
 *   [D2] OUTPUT INDEXING ORIGIN. Given row-major, out[(r-1)*14 + (c-1)] for
 *        input pixel (r,c) is the only mapping that fills 14x14 densely in
 *        raster order, so this follows from [D1] rather than being free.
 *        Recorded because it is a place an implementation could differ
 *        without noticing.
 *
 * DEFINITION USED. The median of nine values is the 5th smallest, i.e. index
 * 4 of the sorted nine, zero-based. For an odd count this is unambiguous and
 * needs no averaging rule.
 *
 * Slow-and-obvious per SPEC §6. The note calls the kernel "sorting-network
 * friendly", which is a hint about what a FAST implementation may do — an
 * oracle should not take it. This uses a plain insertion sort of the nine
 * gathered values, chosen to be read and trusted rather than to be quick.
 */
#include <stdint.h>
#include <stddef.h>

#define IN_DIM  16
#define OUT_DIM 14

void median3x3_u8(const uint8_t in[16*16], uint8_t out[14*14])
{
    for (int r = 1; r <= OUT_DIM; r++) {          /* interior rows 1..14 */
        for (int c = 1; c <= OUT_DIM; c++) {      /* interior cols 1..14 */

            uint8_t w[9];
            int m = 0;

            for (int dr = -1; dr <= 1; dr++) {
                for (int dc = -1; dc <= 1; dc++) {
                    w[m++] = in[(r + dr) * IN_DIM + (c + dc)];   /* [D1] */
                }
            }

            /* insertion sort, nine elements, deliberately plain */
            for (int i = 1; i < 9; i++) {
                const uint8_t key = w[i];
                int j = i - 1;
                while (j >= 0 && w[j] > key) {
                    w[j + 1] = w[j];
                    j--;
                }
                w[j + 1] = key;
            }

            out[(r - 1) * OUT_DIM + (c - 1)] = w[4];   /* 5th smallest [D2] */
        }
    }
}
