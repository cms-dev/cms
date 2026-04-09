#include <cstdio>
int main() {
  int v;
  if (scanf("%d", &v) != 1)
    return 1;
  if (v != 19) {
    printf("%d\n", v + 1);
  } else {
    // Wrong: should be v + 1
    printf("%d\n", v);
  }
  fflush(stdout);
  return 0;
}
