#include <assert.h>
#include <stdio.h>

extern int userfunc(int x);

int main(int argc, char **argv) {
    // The order these are opened is very important. It must match the
    // manager.
    FILE *in = fopen(argv[1], "r");
    FILE *out = fopen(argv[2], "w");
    setvbuf(out, NULL, _IONBF, 0);

    while (1) {
        int n;
        int ret = fscanf(in, "%d", &n);
        assert(ret == 1);
        if (n == 0)
            break;
        fprintf(out, "correct %d\n", userfunc(n));
    }
    return 0;
}
