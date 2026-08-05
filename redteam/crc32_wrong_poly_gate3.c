/* Redteam gate 3 — wrong polynomial, correct structure.
 * Fails full vector set at first vector gate (3_sanitize). Agent B.
 * Note: this is VALUE-wrong, not UB. Distinct from UB-correct-values shape. */
#include <stdint.h>
#include <stddef.h>
uint32_t crc32(const uint8_t *data, size_t n)
{
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < n; i++) {
        crc ^= (uint32_t)data[i];
        for (int b = 0; b < 8; b++) {
            uint32_t mask = (uint32_t)-(int32_t)(crc & 1u);
            crc = (crc >> 1) ^ (0x82F63B78u & mask); /* CRC-32C poly — WRONG */
        }
    }
    return crc ^ 0xFFFFFFFFu;
}
