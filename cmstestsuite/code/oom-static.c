#include <stdio.h>

int big[132108864];

int main() {
    int i;
    // If we don't do this cycle, the compiler is smart enough not to
    // map the array into resident memory.
    for (i = 0; i < 132108864; i++) {
      big[i] = 0;
    }
    scanf("%d", &big[10000]);
    printf("correct %d\n", big[10000]);
    return 0;
}
