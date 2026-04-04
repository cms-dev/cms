#include <stdio.h>
#include <stdlib.h>

int op(int code, int a, int b) {
  printf("protocol violation\n");
  fflush(stdout);
  exit(0);
  return 0;
}
