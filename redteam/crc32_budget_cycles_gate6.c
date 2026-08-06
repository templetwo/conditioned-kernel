/* Redteam gate 6 — cycles_ratio exceeds cycles_ratio_max (3.0).
 * Hard fixture (LN-7 / §13a item 6). Agent B.
 *
 * History of what did not work under this instrument:
 *   - loop of noinline pure CRC: -O3 CSE → ratio ~1.37
 *   - unrolled pure CRC: same CSE (identical args, pure)
 *   - attribute((optimize("O0"))): host clang -Werror unknown attribute
 *   - multi-hundred-k LCG burn: CBMC --unwind 60 unwinding-assertion fail
 *
 * Working design: noinline CRC that WRITES a caller-provided sink each call
 * (pointer side effect defeats purity/CSE). Unrolled N calls so CBMC never
 * sees a trip count > 60. Algebraic cancel (sink-sink) keeps the value
 * surface identical to a single correct CRC.
 */
#include <stdint.h>
#include <stddef.h>

__attribute__((noinline))
uint32_t ecs_crc32_once(const uint8_t *data, size_t n, uint32_t *sink)
{
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < n; i++) {
        crc ^= (uint32_t)data[i];
        for (int b = 0; b < 8; b++) {
            uint32_t mask = (uint32_t)-(int32_t)(crc & 1u);
            crc = (crc >> 1) ^ (0xEDB88320u & mask);
        }
    }
    /* Observable store: prevents treating this as a pure function. */
    *sink ^= crc;
    return crc ^ 0xFFFFFFFFu;
}

uint32_t crc32(const uint8_t *data, size_t n)
{
    uint32_t sink = 0u;
    uint32_t r = 0u;
    r = ecs_crc32_once(data, n, &sink); /* rep 1/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 2/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 3/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 4/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 5/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 6/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 7/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 8/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 9/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 10/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 11/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 12/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 13/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 14/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 15/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 16/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 17/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 18/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 19/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 20/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 21/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 22/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 23/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 24/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 25/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 26/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 27/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 28/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 29/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 30/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 31/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 32/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 33/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 34/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 35/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 36/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 37/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 38/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 39/40 */
    r = ecs_crc32_once(data, n, &sink); /* rep 40/40 */
    return r + (sink - sink);
}
