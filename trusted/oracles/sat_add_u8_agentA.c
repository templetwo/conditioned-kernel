/* ECS P1 oracle — Agent A (Claude Code, Opus 5).
 * kernel: sat_add_u8
 * Sealed against tag prereg-v1 under the hash-and-seal mechanism (SPEC §6
 * amendment, PREREG §8). Authored blind: no Agent B sat_add_u8 seal hash
 * existed on the seat board at authorship, and no Agent B content was read.
 *
 * SPEC §5: void sat_add_u8(const uint8_t*, const uint8_t*, uint8_t*, size_t n)
 * domain n = 256. Unsigned saturating add: out[i] = min(a[i] + b[i], 255).
 *
 * Pointer precondition (SPEC §5, decided option 2, board #13818):
 *   valid iff (ptr != NULL || n == 0). NULL with n > 0 is OUT OF DOMAIN —
 *   undefined, untested, never a vector. This oracle does not guard it and
 *   makes no claim about it.
 *
 * Slow-and-obvious per SPEC §6. Widen to uint16_t so the sum cannot wrap,
 * then clamp. No branchless tricks, no table, no aliasing assumptions
 * beyond what the signature already permits.
 */
#include <stdint.h>
#include <stddef.h>

void sat_add_u8(const uint8_t *a, const uint8_t *b, uint8_t *out, size_t n)
{
    for (size_t i = 0; i < n; i++) {
        /* uint16_t cannot overflow for two uint8_t operands: max 255+255=510. */
        const uint16_t sum = (uint16_t)((uint16_t)a[i] + (uint16_t)b[i]);

        out[i] = (sum > 255u) ? (uint8_t)255u : (uint8_t)sum;
    }
}
