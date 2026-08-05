/* ECS gate 4 — bounded equivalence, crc32.
 * Proves the two independently sealed oracles agree for ALL inputs up to the
 * unwind bound, rather than for sampled inputs. SPEC §7 gate 4: "equivalence
 * vs oracle for small bounded n". */
#include <stdint.h>
#include <stddef.h>
uint32_t crc32_A(const uint8_t *, size_t);
uint32_t crc32_B(const uint8_t *, size_t);
#ifndef NBYTES
#define NBYTES 6
#endif
int main(void) {
    uint8_t d[NBYTES];
    size_t n;
    for (int i = 0; i < NBYTES; i++) d[i] = nondet_uchar();
    n = nondet_size_t();
    __CPROVER_assume(n <= NBYTES);            /* domain: n <= 4096, bounded here */
    __CPROVER_assert(crc32_A(d, n) == crc32_B(d, n), "crc32 oracles equivalent");
    return 0;
}
