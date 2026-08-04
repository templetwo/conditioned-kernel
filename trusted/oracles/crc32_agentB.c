/* ECS P1 oracle — Agent B (Grok Build, grok-4.5)
 * kernel: crc32
 * Sealed against tag prereg-v1. Authored blind: no Agent A oracle content read.
 * Spec (PREREG / SPEC §5): poly 0xEDB88320 reflected, init 0xFFFFFFFF,
 * xorout 0xFFFFFFFF. Check: "123456789" -> 0xCBF43926.
 * Slow-and-obvious: bitwise, no table. Reference quality, not performance.
 */
#include <stdint.h>
#include <stddef.h>

uint32_t crc32(const uint8_t *data, size_t n)
{
    uint32_t crc = 0xFFFFFFFFu;
    size_t i;
    int bit;

    if (data == NULL && n != 0) {
        /* Undefined for null non-empty; treat as empty domain edge. */
        n = 0;
    }

    for (i = 0; i < n; i++) {
        crc ^= (uint32_t)data[i];
        for (bit = 0; bit < 8; bit++) {
            if (crc & 1u) {
                crc = (crc >> 1) ^ 0xEDB88320u;
            } else {
                crc >>= 1;
            }
        }
    }
    return crc ^ 0xFFFFFFFFu;
}
