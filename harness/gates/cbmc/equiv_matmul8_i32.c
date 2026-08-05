/* ECS gate 4 — bounded equivalence, matmul8_i32. Full 8x8, domain-constrained. */
#include <stdint.h>
void mm_A(const int32_t*, const int32_t*, int32_t*);
void mm_B(const int32_t*, const int32_t*, int32_t*);
int main(void){
  int32_t a[64],b[64],ca[64],cb[64];
  for(int i=0;i<64;i++){
    a[i]=nondet_int(); b[i]=nondet_int();
    __CPROVER_assume(a[i]>=-1024 && a[i]<=1023);   /* SPEC §5 declared domain */
    __CPROVER_assume(b[i]>=-1024 && b[i]<=1023);
    ca[i]=0; cb[i]=0;
  }
  mm_A(a,b,ca); mm_B(a,b,cb);
  for(int i=0;i<64;i++) __CPROVER_assert(ca[i]==cb[i], "matmul8_i32 oracles equivalent");
  return 0;
}
