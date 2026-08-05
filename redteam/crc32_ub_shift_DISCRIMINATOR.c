/* NOT A CHAIN FIXTURE. Renamed from crc32_ub_shift_gate3.c.
 *
 * This file uses `volatile`, which is on gate 1's forbidden surface, so
 * chain.run stops it at 1_lint and the sanitizer never fires. Agent B caught
 * that at board #14199 — as a chain fixture claiming gate 3 it was mislabelled,
 * and the FILENAME was the assertion. A name ending _gate3 tells every future
 * sweep and every reader that this reaches gate 3. It does not.
 *
 * What it IS, and what it is kept for: a DISCRIMINATOR proving gates 3 and 5
 * are genuinely different builds when run directly through vector_check, which
 * bypasses gate 1:
 *
 *   --cc "-O3 -mcpu=native"                          exit 0  ACCEPTS
 *   --cc "-O1 -g -fsanitize=undefined,address ..."   exit 1  REJECTS
 *       runtime error: shift exponent 32 is too large for 32-bit type 'int'
 *
 * The chain-valid gate-3 fixture is crc32_ub_shift_chain_gate3.c, authored by
 * Agent B without volatile.
 */
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
