#include <stdio.h>

int main() {
    int n;
    FILE *in = fopen("input.txt", "r");
    FILE *out = fopen("output.txt", "w");
    fscanf(in, "%d", &n);
    fprintf(out, "correct %d\n", n % 2 ? n : 0);
    return 0;
}
