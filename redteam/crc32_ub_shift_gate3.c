/* Candidate with REAL UB that is invisible to the measurement build:
 * a shift past the width of int. Correct values are still produced at -O3,
 * so gate 5 passes it. UBSan traps it, so gate 3 must reject it.
 * This is the shape a genuine gate-3 redteam fixture must have. */
#include <stdint.h>
#include <stddef.h>
uint32_t crc32(const uint8_t *data, size_t n)
{
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < n; i++) {
        int w = 32;
        volatile int poison = 1 << w;      /* UB: shift >= width of int */
        (void)poison;
        crc ^= (uint32_t)data[i];
        for (int b = 0; b < 8; b++) {
            uint32_t mask = (uint32_t)-(int32_t)(crc & 1u);
            crc = (crc >> 1) ^ (0xEDB88320u & mask);
        }
    }
    return crc ^ 0xFFFFFFFFu;
}
