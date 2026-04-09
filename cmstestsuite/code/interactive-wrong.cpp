#include <assert.h>
int op(int code, int a, int b) {
  if (code == 0)
    return a * b;
  else if (code == 1)
    return a + b;
  else
    assert(false);
  return 0;
}
