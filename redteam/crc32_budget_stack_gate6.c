/* Redteam gate 6 — stack_bytes exceeds stack_bytes_max (1024).
 * Correct CRC values; large automatic array in a noinline helper that is only
 * called on an unreachable domain edge so gate 5 stays green. Stack usage is
 * measured per-function via -fstack-usage (chain.gate6_budget), so the helper's
 * frame is enough. Agent B. */
#include <stdint.h>
#include <stddef.h>

__attribute__((noinline))
uint32_t ecs_stack_ballast(uint32_t c)
{
    /* Cap is 1024; this frame is deliberately larger. Touch every page-ish so
     * the array is not DCE'd out of the frame. */
    uint8_t pad[8192];
    for (size_t i = 0; i < sizeof pad; i++)
        pad[i] = (uint8_t)(c + (uint32_t)i);
    return c ^ (uint32_t)pad[0] ^ (uint32_t)pad[sizeof pad - 1u];
}

uint32_t crc32(const uint8_t *data, size_t n)
{
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < n; i++) {
        crc ^= (uint32_t)data[i];
        for (int b = 0; b < 8; b++) {
            uint32_t mask = (uint32_t)-(int32_t)(crc & 1u);
            crc = (crc >> 1) ^ (0xEDB88320u & mask);
        }
    }
    /* Unreachable for any in-domain n (n_max 4096). Keeps the helper linked. */
    if (n == ~(size_t)0)
        crc = ecs_stack_ballast(crc);
    return crc ^ 0xFFFFFFFFu;
}
