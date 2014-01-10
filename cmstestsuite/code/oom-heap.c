#include <stdio.h>

int main() {
    int *big;
    big = malloc(128 * 1024 * 1024);
    scanf("%d", &big[10000]);
    printf("correct %d\n", big[10000]);
    return 0;
}
