/* ECS P1 — crc32 oracle, Agent A (Claude Code, Opus 5).
 * Authored blind under the hash-and-seal mechanism frozen at thread #20
 * and recorded in PREREG v1 §8 (tag prereg-v1). Written before any Agent B
 * oracle content was seen; no seal hash from Agent B existed at authorship.
 *
 * SPEC §5 closed spec: reflected poly 0xEDB88320, init 0xFFFFFFFF,
 * xorout 0xFFFFFFFF. Published check: "123456789" -> 0xCBF43926.
 * SPEC §6 asks for slow-and-obvious. No table, no unrolling, no branching
 * on data — the bit loop is written to be read, not to be fast.
 */
#include <stdint.h>
#include <stddef.h>

uint32_t crc32(const uint8_t *data, size_t n)
{
    uint32_t crc = 0xFFFFFFFFu;

    for (size_t i = 0; i < n; i++) {
        /* Reflected algorithm: message bits enter at the LSB end. */
        crc ^= (uint32_t)data[i];

        for (unsigned bit = 0; bit < 8; bit++) {
            /* Branchless conditional XOR: mask is all-ones when the
             * outgoing bit is 1, all-zeros otherwise. Avoids an if so the
             * control flow cannot depend on message content. */
            const uint32_t lsb  = crc & 1u;
            const uint32_t mask = (uint32_t)0u - lsb;
            crc = (crc >> 1) ^ (0xEDB88320u & mask);
        }
    }

    return crc ^ 0xFFFFFFFFu;
}
