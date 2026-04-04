#include <cstdio>
int main() {
  int v;
  if (scanf("%d", &v) != 1)
    return 1;
  printf("-1\n"); // Definitely not v+1
  fflush(stdout);
  return 0;
}
