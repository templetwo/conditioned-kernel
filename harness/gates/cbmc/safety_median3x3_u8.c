/* ECS gate 4, memory-safety half — median3x3_u8. */
#include <stdint.h>
void median3x3_u8(const uint8_t*, uint8_t*);
int main(void){
  uint8_t in[256], out[196];
  for (int i=0;i<256;i++) in[i]=nondet_uchar();
  median3x3_u8(in,out);
  return 0;
}
