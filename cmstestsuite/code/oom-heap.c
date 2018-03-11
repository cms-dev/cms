#include <stdio.h>

int main() {
    int *big;
    int i;
    big = malloc(125 * 1000 * 1000);
    // If we don't do this cycle, the compiler is smart enough not to
    // map the array into resident memory.
    for (i = 0; i < 125 * 1000 * 1000 / sizeof(int); i++) {
      big[i] = 0;
    }
    scanf("%d", &big[10000]);
    printf("correct %d\n", big[10000]);
    return 0;
}
