#include <assert.h>
#include <stdio.h>

extern int userfunc(int x);

int main(int argc, char **argv) {
    while (1) {
        int n;
        int ret = scanf("%d", &n);
        assert(ret == 1);
        if (n == 0)
            break;
        printf("correct %d\n", n + 1);
        fflush(stdout);
    }
    return 0;
}
