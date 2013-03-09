#include <stdio.h>

int main() {
    int n;
    FILE *in = fopen("input.txt", "r");
    FILE *out = fopen("output.txt", "w");
    fscanf(in, "%d", &n);
    return 0;
}
