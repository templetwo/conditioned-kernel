/* ECS P0 bench harness (SPEC §8). timing_source = "clock":
 * perf is absent on this device, so clock_gettime(CLOCK_MONOTONIC_RAW)
 * under pinned clocks per the SPEC §4 fallback note. Emits JSON. */
#define _POSIX_C_SOURCE 199309L
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <string.h>

uint32_t crc32_ref(const uint8_t *data, size_t n);

#define WARMUP   200
#define MEASURED 1000
#define BATCHES  10
#define NBYTES   4096

static int cmp_d(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}
static double median(double *v, int n) {
    qsort(v, (size_t)n, sizeof(double), cmp_d);
    return (n & 1) ? v[n/2] : 0.5 * (v[n/2 - 1] + v[n/2]);
}

int main(void)
{
    static uint8_t buf[NBYTES];
    for (int i = 0; i < NBYTES; i++) buf[i] = (uint8_t)(i * 31 + 7);

    /* correctness gate before any timing is trusted */
    const char *chk = "123456789";
    uint32_t got = crc32_ref((const uint8_t *)chk, 9);
    if (got != 0xCBF43926u) {
        fprintf(stderr, "CHECK FAIL: got 0x%08X want 0xCBF43926\n", got);
        return 2;
    }

    volatile uint32_t sink = 0;
    for (int i = 0; i < WARMUP; i++) sink ^= crc32_ref(buf, NBYTES);

    double batch_med[BATCHES];
    static double s[MEASURED];
    for (int b = 0; b < BATCHES; b++) {
        for (int i = 0; i < MEASURED; i++) {
            struct timespec t0, t1;
            clock_gettime(CLOCK_MONOTONIC_RAW, &t0);
            sink ^= crc32_ref(buf, NBYTES);
            clock_gettime(CLOCK_MONOTONIC_RAW, &t1);
            s[i] = (double)(t1.tv_sec - t0.tv_sec) * 1e9
                 + (double)(t1.tv_nsec - t0.tv_nsec);
        }
        batch_med[b] = median(s, MEASURED);
    }

    double tmp[BATCHES];
    memcpy(tmp, batch_med, sizeof tmp);
    double overall = median(tmp, BATCHES);
    double mn = batch_med[0], mx = batch_med[0];
    for (int b = 1; b < BATCHES; b++) {
        if (batch_med[b] < mn) mn = batch_med[b];
        if (batch_med[b] > mx) mx = batch_med[b];
    }
    double spread_pct = (overall > 0.0) ? (mx - mn) / overall * 100.0 : -1.0;

    double ad[BATCHES];
    for (int b = 0; b < BATCHES; b++) {
        double d = batch_med[b] - overall;
        ad[b] = d < 0 ? -d : d;
    }
    double mad = median(ad, BATCHES);

    printf("{\n");
    printf("  \"timing_source\": \"clock\",\n");
    printf("  \"clock\": \"CLOCK_MONOTONIC_RAW\",\n");
    printf("  \"kernel_id\": \"crc32\",\n");
    printf("  \"check_value_ok\": true,\n");
    printf("  \"nbytes\": %d, \"warmup\": %d, \"measured\": %d, \"batches\": %d,\n",
           NBYTES, WARMUP, MEASURED, BATCHES);
    printf("  \"batch_medians_ns\": [");
    for (int b = 0; b < BATCHES; b++) printf("%s%.1f", b ? ", " : "", batch_med[b]);
    printf("],\n");
    printf("  \"median_ns\": %.1f,\n", overall);
    printf("  \"mad_ns\": %.1f,\n", mad);
    printf("  \"spread_pct\": %.4f,\n", spread_pct);
    printf("  \"stability_gate_2pct\": %s,\n", spread_pct <= 2.0 ? "true" : "false");
    printf("  \"sink\": %u\n", (unsigned)sink);
    printf("}\n");
    return spread_pct <= 2.0 ? 0 : 1;
}
