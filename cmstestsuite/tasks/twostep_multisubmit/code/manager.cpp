#include <stdio.h>

#include "manager.h"

extern int userfuncA(int x);
extern int userfuncB(int x);

int main(int argc, char **argv) {
    int n;
    if (argv[1][0] == '0') {
        FILE *in = fopen("input.txt", "r");
        FILE *out = fopen(argv[2], "w");
        fscanf(in, "%d", &n);
        fprintf(out, "%d\n", userfuncA(n));

    } else if (argv[1][0] == '1') {
        FILE *in = fopen(argv[2], "r");
        FILE *out = fopen("output.txt", "w");
        fscanf(in, "%d", &n);
        fprintf(out, "correct %d\n", userfuncB(n));
    }
    return 0;
}
