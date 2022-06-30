#include <stdio.h>
#include <stdlib.h>

int *big;

int main() {
    int i;
    big = malloc(128 * 1024 * 1024);
    // If we don't do this cycle, the compiler is smart enough not to
    // map the array into resident memory.
    for (i = 0; i < 128 * 1024 * 1024 / sizeof(int); i++) {
      big[i] = 0;
    }
    scanf("%d", &big[10000]);
    printf("correct %d\n", big[10000]);
    return 0;
}
