/* ECS gate 4 — bounded equivalence, sat_add_u8. */
#include <stdint.h>
#include <stddef.h>
void sat_add_A(const uint8_t*, const uint8_t*, uint8_t*, size_t);
void sat_add_B(const uint8_t*, const uint8_t*, uint8_t*, size_t);
#ifndef NB
#define NB 4
#endif
int main(void){
  uint8_t a[NB],b[NB],oa[NB],ob[NB]; size_t n;
  for(int i=0;i<NB;i++){a[i]=nondet_uchar();b[i]=nondet_uchar();oa[i]=0;ob[i]=0;}
  n=nondet_size_t(); __CPROVER_assume(n<=NB);
  sat_add_A(a,b,oa,n); sat_add_B(a,b,ob,n);
  for(int i=0;i<NB;i++) __CPROVER_assert(i>=(int)n || oa[i]==ob[i], "sat_add_u8 oracles equivalent");
  return 0;
}
