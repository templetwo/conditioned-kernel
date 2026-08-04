/* ECS P1 — dual-oracle agreement for sat_add_u8 (SPEC §6).
 * Domain per SPEC §5: n = 256, pointers valid (NULL with n>0 is out of domain,
 * decided #13818, so it is not tested here). */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
void sat_add_A(const uint8_t*, const uint8_t*, uint8_t*, size_t);
void sat_add_B(const uint8_t*, const uint8_t*, uint8_t*, size_t);
static uint64_t s_ = 0x9E3779B97F4A7C15ull;
static uint32_t xs(void){ s_^=s_<<13; s_^=s_>>7; s_^=s_<<17; return (uint32_t)(s_>>32); }
int main(void){
  uint8_t a[256],b[256],oa[256],ob[256]; long cases=0,dis=0;
  /* exhaustive: every (a,b) byte pair, 65536 combinations */
  for(int x=0;x<256;x++){
    for(int y=0;y<256;y++){a[y]=(uint8_t)x;b[y]=(uint8_t)y;}
    sat_add_A(a,b,oa,256); sat_add_B(a,b,ob,256);
    for(int y=0;y<256;y++){cases++;if(oa[y]!=ob[y]){dis++;if(dis<4)printf("  DISAGREE %d+%d A=%u B=%u\n",x,y,oa[y],ob[y]);}}
  }
  /* seeded random */
  for(int t=0;t<20000;t++){
    for(int i=0;i<256;i++){a[i]=(uint8_t)xs();b[i]=(uint8_t)xs();}
    sat_add_A(a,b,oa,256); sat_add_B(a,b,ob,256);
    for(int i=0;i<256;i++){cases++;if(oa[i]!=ob[i])dis++;}
  }
  /* n=0 must write nothing */
  for(int i=0;i<256;i++){oa[i]=0xAA;ob[i]=0xAA;}
  sat_add_A(a,b,oa,0); sat_add_B(a,b,ob,0);
  int n0=(oa[0]==0xAA&&ob[0]==0xAA);
  printf("n=0 writes nothing: %s\n", n0?"PASS":"FAIL");
  printf("cases=%ld disagreements=%ld -> %s\n",cases,dis,dis?"ORACLES DISAGREE":"ORACLES AGREE");
  return (dis||!n0)?1:0;
}
