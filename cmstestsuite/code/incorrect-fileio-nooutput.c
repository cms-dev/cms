#include <stdio.h>

int main() {
    int n;
    FILE *in = fopen("input.txt", "r");
    fscanf(in, "%d", &n);
    return 0;
}
