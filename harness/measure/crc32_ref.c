/* ECS P0 reference CRC32 — Agent A blind implementation.
 * Written 2026-08-04 before any trusted/oracles/ content existed or was read.
 * Fully closed spec (SPEC §5): poly 0xEDB88320 reflected, init 0xFFFFFFFF,
 * xorout 0xFFFFFFFF. Check: "123456789" -> 0xCBF43926.
 * Deliberately slow-and-obvious: bitwise, no table. */
#include <stdint.h>
#include <stddef.h>

uint32_t crc32_ref(const uint8_t *data, size_t n)
{
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < n; i++) {
        crc ^= (uint32_t)data[i];
        for (int b = 0; b < 8; b++) {
            uint32_t mask = (uint32_t)-(int32_t)(crc & 1u);
            crc = (crc >> 1) ^ (0xEDB88320u & mask);
        }
    }
    return crc ^ 0xFFFFFFFFu;
}
