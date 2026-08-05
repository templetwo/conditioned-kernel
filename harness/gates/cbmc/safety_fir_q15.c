/* ECS gate 4, memory-safety half — fir_q15, one oracle at a time.
 * Equivalence between the two oracles is intractable at full size (measured);
 * memory safety for a single oracle over nondeterministic in-domain input is
 * not. SPEC §7 gate 4 asks for both, so this delivers the half that is
 * provable here and the equivalence half is reported separately. */
#include <stdint.h>
void fir_q15(const int16_t*, const int16_t*, int16_t*);
int main(void){
  int16_t x[256], h[16], y[256];
  for (int i=0;i<256;i++) x[i]=(int16_t)nondet_short();
  for (int k=0;k<16;k++)  h[k]=(int16_t)nondet_short();
  fir_q15(x,h,y);
  return 0;
}
