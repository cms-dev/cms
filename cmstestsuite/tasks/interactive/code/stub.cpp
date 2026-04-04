#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

int op(int code, int a, int b);

int main() {
  int a, b;
  if (scanf("%d %d", &a, &b) != 2) {
    return 1;
  }
  printf("%d\n", op(0, a, b));
  fflush(stdout);

  if (scanf("%d %d", &a, &b) != 2)
    return 1;
  printf("%d\n", op(1, a, b));
  fflush(stdout);

  return 0;
}
