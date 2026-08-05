/* Redteam gate 3 (chain-valid). UB left-shift past width; CRC values remain correct.
 * Intended chain stop: 3_sanitize. Agent B rework of the harness discriminator
 * so the fixture survives the forbidden-surface lint and reaches UBSan on device.
 */
#include <stdint.h>
#include <stddef.h>

int ecs_rt_shl(int a, int b)
{
    return a << b;
}

uint32_t crc32(const uint8_t *data, size_t n)
{
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < n; i++) {
        int w = 32 + (int)(n - n);
        int poison = ecs_rt_shl(1, w);
        crc ^= (uint32_t)data[i] ^ (uint32_t)(poison & 0);
        for (int b = 0; b < 8; b++) {
            uint32_t mask = (uint32_t)-(int32_t)(crc & 1u);
            crc = (crc >> 1) ^ (0xEDB88320u & mask);
        }
    }
    return crc ^ 0xFFFFFFFFu;
}
