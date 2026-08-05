/* ECS P1 — dual-oracle agreement for fir_q15 (SPEC §6).
 * Targets the four unpinned bits named at board #14001: boundary handling,
 * accumulator width, saturation placement, rounding. */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
void fir_A(const int16_t*, const int16_t*, int16_t*);
void fir_B(const int16_t*, const int16_t*, int16_t*);
static uint64_t s_=0xDEADBEEFCAFEF00Dull;
static uint32_t xs(void){s_^=s_<<13;s_^=s_>>7;s_^=s_<<17;return (uint32_t)(s_>>32);}
static int16_t ya[256], yb[256];
static long cases=0, dis=0;
static void cmp(const int16_t*x,const int16_t*h,const char*lbl){
  memset(ya,0x5A,sizeof ya); memset(yb,0x5A,sizeof yb);
  fir_A(x,h,ya); fir_B(x,h,yb); cases++;
  if(memcmp(ya,yb,sizeof ya)){
    dis++;
    for(int i=0;i<256;i++) if(ya[i]!=yb[i]){
      printf("  DISAGREE %-22s first at y[%d]: A=%d B=%d\n",lbl,i,ya[i],yb[i]); break; }
  }
}
int main(void){
  int16_t x[256],h[16];
  /* extremes that stress accumulator width [A2] */
  const int16_t ext[4]={0,1,32767,-32768};
  for(int a=0;a<4;a++)for(int b=0;b<4;b++){
    for(int i=0;i<256;i++)x[i]=ext[a]; for(int k=0;k<16;k++)h[k]=ext[b];
    cmp(x,h,"extreme const");
  }
  /* warm-up boundary [A1]: impulse at each of the first 32 positions */
  for(int p=0;p<32;p++){
    memset(x,0,sizeof x); memset(h,0,sizeof h);
    x[p]=32767; for(int k=0;k<16;k++)h[k]=(int16_t)(1000*(k+1));
    cmp(x,h,"impulse warmup");
  }
  /* alternating signs: exercises truncation direction [A4] */
  for(int t=0;t<64;t++){
    for(int i=0;i<256;i++)x[i]=(int16_t)((i+t)%2?-32768:32767);
    for(int k=0;k<16;k++)h[k]=(int16_t)((k%2)?-(t*257+1):(t*257+1));
    cmp(x,h,"alternating sign");
  }
  /* small magnitudes near the shift boundary: |acc>>15| in {-1,0,1} */
  for(int t=0;t<2000;t++){
    for(int i=0;i<256;i++)x[i]=(int16_t)((int)(xs()%512)-256);
    for(int k=0;k<16;k++)h[k]=(int16_t)((int)(xs()%512)-256);
    cmp(x,h,"near-zero shift");
  }
  /* full random */
  for(int t=0;t<20000;t++){
    for(int i=0;i<256;i++)x[i]=(int16_t)xs();
    for(int k=0;k<16;k++)h[k]=(int16_t)xs();
    cmp(x,h,"random");
  }
  printf("\nvector-sets=%ld disagreements=%ld -> %s\n",cases,dis,dis?"ORACLES DISAGREE":"ORACLES AGREE");
  return dis?1:0;
}
