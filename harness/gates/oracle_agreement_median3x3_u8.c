/* ECS P1 — dual-oracle agreement for median3x3_u8 (SPEC §6).
 * Unpinned bit [D1]: layout. A transposed reading still computes a 3x3
 * median, just of the transposed image, so it agrees on symmetric inputs
 * and diverges otherwise — asymmetric probes are required to separate. */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
void med_A(const uint8_t*, uint8_t*);
void med_B(const uint8_t*, uint8_t*);
static uint64_t s_=0xFEEDFACEC0FFEEull;
static uint32_t xs(void){s_^=s_<<13;s_^=s_>>7;s_^=s_<<17;return (uint32_t)(s_>>32);}
static uint8_t oa[196], ob[196];
static long cases=0, dis=0;
static void cmp(const uint8_t*in,const char*lbl){
  memset(oa,0x5A,sizeof oa); memset(ob,0x5A,sizeof ob);
  med_A(in,oa); med_B(in,ob); cases++;
  if(memcmp(oa,ob,sizeof oa)){dis++;
    for(int i=0;i<196;i++) if(oa[i]!=ob[i]){
      printf("  DISAGREE %-18s first at out[%d] (r=%d,c=%d): A=%d B=%d\n",lbl,i,i/14,i%14,oa[i],ob[i]);break;}}
}
static uint8_t in[256];
int main(void){
  /* strongly ASYMMETRIC: horizontal gradient. A transposed reading gives a
     vertical gradient and must disagree almost everywhere. */
  for(int r=0;r<16;r++)for(int c=0;c<16;c++) in[r*16+c]=(uint8_t)(c*16);
  cmp(in,"horizontal ramp");
  for(int r=0;r<16;r++)for(int c=0;c<16;c++) in[r*16+c]=(uint8_t)(r*16);
  cmp(in,"vertical ramp");
  /* single bright pixel at every asymmetric position */
  for(int p=0;p<256;p++){
    memset(in,10,sizeof in); in[p]=255; cmp(in,"single impulse");
  }
  /* single dark pixel */
  for(int p=0;p<256;p++){
    memset(in,200,sizeof in); in[p]=0; cmp(in,"single dark");
  }
  /* two-value checkerboards and stripes: median ties and ordering edges */
  for(int r=0;r<16;r++)for(int c=0;c<16;c++) in[r*16+c]=(uint8_t)(((r+c)&1)?255:0);
  cmp(in,"checkerboard");
  for(int r=0;r<16;r++)for(int c=0;c<16;c++) in[r*16+c]=(uint8_t)((c&1)?255:0);
  cmp(in,"vertical stripes");
  for(int r=0;r<16;r++)for(int c=0;c<16;c++) in[r*16+c]=(uint8_t)((r&1)?255:0);
  cmp(in,"horizontal stripes");
  /* saturated extremes and constants */
  memset(in,0,sizeof in);   cmp(in,"all zero");
  memset(in,255,sizeof in); cmp(in,"all max");
  /* random */
  for(int t=0;t<20000;t++){
    for(int i=0;i<256;i++) in[i]=(uint8_t)xs();
    cmp(in,"random");
  }
  printf("\nimages=%ld disagreements=%ld -> %s\n",cases,dis,dis?"ORACLES DISAGREE":"ORACLES AGREE");
  return dis?1:0;
}
