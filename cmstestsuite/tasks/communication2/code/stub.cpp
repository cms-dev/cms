#include <assert.h>
#include <stdio.h>

extern int userfunc1(int x);
extern int userfunc2(int x);

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
        if(argv[3][0] == '0')
            fprintf(out, "correct %d\n", userfunc1(n));
        else
            fprintf(out, "correct %d\n", userfunc2(n));
    }
    return 0;
}
