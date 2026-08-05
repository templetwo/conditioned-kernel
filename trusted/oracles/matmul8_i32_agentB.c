/* ECS P1 oracle — Agent B (Grok Build, grok-4.5)
 * kernel: matmul8_i32
 * Sealed against tag prereg-v1. Authored blind: no Agent A oracle content read.
 * Spec: void matmul8_i32(const int32_t a[64], const int32_t b[64], int32_t c[64])
 * Domain: entries in [-1024, 1023] — products fit int32 with headroom.
 * Layout reading (SPEC silent): 8x8 ROW-MAJOR. a[i*8+k] * b[k*8+j] -> c[i*8+j].
 * Column-major would be a departure the C flat-array signature does not signal.
 * No saturation. No NULL guards (option 2).
 */
#include <stdint.h>

void matmul8_i32(const int32_t a[64], const int32_t b[64], int32_t c[64])
{
    int i, j, k;
    for (i = 0; i < 8; i++) {
        for (j = 0; j < 8; j++) {
            int32_t sum = 0;
            for (k = 0; k < 8; k++) {
                sum += a[i * 8 + k] * b[k * 8 + j];
            }
            c[i * 8 + j] = sum;
        }
    }
}
