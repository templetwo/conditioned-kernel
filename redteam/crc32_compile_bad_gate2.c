/* Redteam gate 2 — will not compile under -Werror. Must stop at 2_compile. Agent B. */
#include <stdint.h>
#include <stddef.h>
uint32_t crc32(const uint8_t *data, size_t n)
{
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < n; i++) {
        crc ^= data[i];
        for (int b = 0; b < 8; b++) {
            uint32_t mask = (uint32_t)-(int32_t)(crc & 1u);
            crc = (crc >> 1) ^ (0xEDB88320u & mask);
        }
    }
    return this_is_not_defined; /* deliberate undeclared identifier */
}
