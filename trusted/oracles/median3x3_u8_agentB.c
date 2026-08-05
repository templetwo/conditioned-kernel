/* ECS P1 oracle — Agent B (Grok Build, grok-4.5)
 * kernel: median3x3_u8
 * Sealed against tag prereg-v1. Authored blind: no Agent A median content read.
 * Spec: void median3x3_u8(const uint8_t in[16*16], uint8_t out[14*14])
 * Domain: interior only — out is 14x14 over centers (r,c) in [1..14]x[1..14]
 * of the 16x16 input (0-based). Each out value is the median of the 3x3 window.
 * Median of 9: sort ascending, take index 4.
 * Layout: row-major, in[r*16+c], out[or*14+oc] with or=r-1, oc=c-1.
 * No NULL guards (option 2). Slow-and-obvious.
 */
#include <stdint.h>

static void sort9(uint8_t v[9])
{
    /* insertion sort */
    int i, j;
    for (i = 1; i < 9; i++) {
        uint8_t key = v[i];
        j = i - 1;
        while (j >= 0 && v[j] > key) {
            v[j + 1] = v[j];
            j--;
        }
        v[j + 1] = key;
    }
}

void median3x3_u8(const uint8_t in[256], uint8_t out[196])
{
    int r, c, dr, dc, k;
    for (r = 1; r <= 14; r++) {
        for (c = 1; c <= 14; c++) {
            uint8_t win[9];
            k = 0;
            for (dr = -1; dr <= 1; dr++) {
                for (dc = -1; dc <= 1; dc++) {
                    win[k++] = in[(r + dr) * 16 + (c + dc)];
                }
            }
            sort9(win);
            out[(r - 1) * 14 + (c - 1)] = win[4];
        }
    }
}
