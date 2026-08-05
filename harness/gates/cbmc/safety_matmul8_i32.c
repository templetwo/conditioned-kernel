/* ECS gate 4, memory-safety half — matmul8_i32, inputs constrained to the
 * SPEC §5 declared domain so the overflow check tests the REAL claim: that
 * the domain bound keeps every row-column sum inside int32. */
#include <stdint.h>
void matmul8_i32(const int32_t*, const int32_t*, int32_t*);
int main(void){
  int32_t a[64], b[64], c[64];
  for (int i=0;i<64;i++){
    a[i]=nondet_int(); b[i]=nondet_int();
    __CPROVER_assume(a[i]>=-1024 && a[i]<=1023);
    __CPROVER_assume(b[i]>=-1024 && b[i]<=1023);
  }
  matmul8_i32(a,b,c);
  return 0;
}
