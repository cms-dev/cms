#include <stdio.h>

int main() {
    int n;
    scanf("%d", &n);
    printf("correct %d\n", n % 2 ? n : 0);
    return 0;
}
