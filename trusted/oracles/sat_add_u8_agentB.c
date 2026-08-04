/* ECS P1 oracle — Agent B (Grok Build, grok-4.5)
 * kernel: sat_add_u8
 * Sealed against tag prereg-v1. Authored blind: no Agent A oracle content read.
 * Spec: void sat_add_u8(const uint8_t *a, const uint8_t *b, uint8_t *out, size_t n)
 * Domain: n = 256 (SPEC §5). Saturating unsigned 8-bit add: out[i] = min(255, a[i]+b[i]).
 * Pointers valid and non-null for n > 0 (precondition option 2). NULL+n>0 out of domain.
 * Slow-and-obvious reference. No tables.
 */
#include <stdint.h>
#include <stddef.h>

void sat_add_u8(const uint8_t *a, const uint8_t *b, uint8_t *out, size_t n)
{
    size_t i;
    for (i = 0; i < n; i++) {
        unsigned sum = (unsigned)a[i] + (unsigned)b[i];
        out[i] = (sum > 255u) ? (uint8_t)255u : (uint8_t)sum;
    }
}
