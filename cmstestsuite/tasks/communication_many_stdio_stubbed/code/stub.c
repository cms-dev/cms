#include <assert.h>
#include <stdio.h>

extern int userfunc1(int x);
extern int userfunc2(int x);

int main(int argc, char **argv) {
    while (1) {
        int n;
        int ret = scanf("%d", &n);
        assert(ret == 1);
        if (n == 0)
            break;
        if(argv[1][0] == '0')
            printf("correct %d\n", userfunc1(n));
        else
            printf("correct %d\n", userfunc2(n));
        fflush(stdout);
    }
    return 0;
}
