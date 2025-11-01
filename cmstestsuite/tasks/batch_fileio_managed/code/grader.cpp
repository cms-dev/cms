#include <stdio.h>

extern int userfunc(int x);

int main() {
    int n;
    FILE *in = fopen("input.txt", "r");
    FILE *out = fopen("output.txt", "w");
    fscanf(in, "%d", &n);
    fprintf(out, "correct %d\n", userfunc(n));
    return 0;
}
