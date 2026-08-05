/* ECS P1 — dual-oracle agreement for matmul8_i32 (SPEC §6).
 * Targets the single unpinned bit named at board #14025: memory layout.
 * A column-major reading yields the transpose, so non-symmetric inputs
 * separate the two conventions immediately. */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
void mm_A(const int32_t*, const int32_t*, int32_t*);
void mm_B(const int32_t*, const int32_t*, int32_t*);
static uint64_t s_=0x123456789ABCDEFull;
static uint32_t xs(void){s_^=s_<<13;s_^=s_>>7;s_^=s_<<17;return (uint32_t)(s_>>32);}
static int32_t ca[64], cb[64];
static long cases=0, dis=0;
static void cmp(const int32_t*a,const int32_t*b,const char*lbl){
  memset(ca,0x5A,sizeof ca); memset(cb,0x5A,sizeof cb);
  mm_A(a,b,ca); mm_B(a,b,cb); cases++;
  if(memcmp(ca,cb,sizeof ca)){dis++;
    for(int i=0;i<64;i++) if(ca[i]!=cb[i]){
      printf("  DISAGREE %-20s first at c[%d] (r=%d,c=%d): A=%d B=%d\n",lbl,i,i/8,i%8,ca[i],cb[i]);break;}}
}
static int32_t A[64],B[64];
int main(void){
  /* single-element probes: every (position, position) pair. A transposed
     reading lands the product in a different cell for all non-diagonal cases. */
  for(int p=0;p<64;p++)for(int q=0;q<64;q++){
    memset(A,0,sizeof A); memset(B,0,sizeof B);
    A[p]=1; B[q]=1; cmp(A,B,"single-element");
  }
  /* domain extremes */
  const int32_t ext[3]={-1024,0,1023};
  for(int x=0;x<3;x++)for(int y=0;y<3;y++){
    for(int i=0;i<64;i++){A[i]=ext[x];B[i]=ext[y];}
    cmp(A,B,"extreme const");
  }
  /* deliberately NON-SYMMETRIC: upper-triangular times lower-triangular */
  memset(A,0,sizeof A); memset(B,0,sizeof B);
  for(int i=0;i<8;i++)for(int j=0;j<8;j++){
    if(j>=i)A[i*8+j]=(int32_t)(i*8+j-500);
    if(j<=i)B[i*8+j]=(int32_t)(1000-i*8-j);
  }
  cmp(A,B,"triangular");
  /* random over the declared domain */
  for(int t=0;t<20000;t++){
    for(int i=0;i<64;i++){A[i]=(int32_t)(xs()%2048)-1024;B[i]=(int32_t)(xs()%2048)-1024;}
    cmp(A,B,"random in-domain");
  }
  printf("\nmatrix-pairs=%ld disagreements=%ld -> %s\n",cases,dis,dis?"ORACLES DISAGREE":"ORACLES AGREE");
  return dis?1:0;
}
