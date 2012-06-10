#include <stdio.h>

int main() {
    int n;
    freopen("input.txt", "r", stdin);
    freopen("output.txt", "w", stdout);
    scanf("%d", &n);
    printf("correct %d\n", n);
    return 0;
}
