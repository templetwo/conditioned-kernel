/* ECS P1 — dual-oracle agreement test for crc32 (SPEC §6).
 * Trust = pairwise agreement + published check value. Disagreement resolves
 * by the published value and CBMC, never by discussion between seats.
 * Domain per SPEC §5: n <= 4096, valid pointer. */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

uint32_t crc32_A(const uint8_t *, size_t);
uint32_t crc32_B(const uint8_t *, size_t);

static uint64_t rng_s = 0x243F6A8885A308D3ull;      /* fixed seed: reproducible */
static uint32_t xs(void) {
    rng_s ^= rng_s << 13; rng_s ^= rng_s >> 7; rng_s ^= rng_s << 17;
    return (uint32_t)(rng_s >> 32);
}

static int cases = 0, disagree = 0;

static void cmp(const uint8_t *p, size_t n, const char *label) {
    uint32_t a = crc32_A(p, n), b = crc32_B(p, n);
    cases++;
    if (a != b) {
        disagree++;
        printf("  DISAGREE %-22s n=%-5zu A=0x%08X B=0x%08X\n", label, n, a, b);
    }
}

int main(void) {
    static uint8_t buf[4096];

    /* published check value — the external anchor, not a self-comparison */
    uint32_t ca = crc32_A((const uint8_t *)"123456789", 9);
    uint32_t cb = crc32_B((const uint8_t *)"123456789", 9);
    printf("published check 0xCBF43926:  A=0x%08X %s   B=0x%08X %s\n",
           ca, ca == 0xCBF43926u ? "PASS" : "FAIL",
           cb, cb == 0xCBF43926u ? "PASS" : "FAIL");

    /* edge cases */
    cmp(buf, 0, "empty");
    memset(buf, 0x00, sizeof buf); cmp(buf, 1, "single 0x00");
    memset(buf, 0xFF, sizeof buf); cmp(buf, 1, "single 0xFF");
    memset(buf, 0x00, sizeof buf); cmp(buf, 4096, "all zero max n");
    memset(buf, 0xFF, sizeof buf); cmp(buf, 4096, "all ones max n");
    for (int i = 0; i < 256; i++) buf[i] = (uint8_t)i;
    cmp(buf, 256, "0..255 ramp");

    /* every single-byte value */
    for (int v = 0; v < 256; v++) { buf[0] = (uint8_t)v; cmp(buf, 1, "single byte sweep"); }

    /* every length 0..4096 with a fixed pattern */
    for (size_t i = 0; i < sizeof buf; i++) buf[i] = (uint8_t)(i * 31 + 7);
    for (size_t n = 0; n <= 4096; n++) cmp(buf, n, "length sweep");

    /* seeded random content, random lengths */
    for (int t = 0; t < 20000; t++) {
        size_t n = xs() % 4097;
        for (size_t i = 0; i < n; i++) buf[i] = (uint8_t)xs();
        cmp(buf, n, "random");
    }

    printf("\ncases=%d disagreements=%d -> %s\n", cases, disagree,
           disagree == 0 ? "ORACLES AGREE" : "ORACLES DISAGREE");
    return (disagree == 0 && ca == 0xCBF43926u && cb == 0xCBF43926u) ? 0 : 1;
}
