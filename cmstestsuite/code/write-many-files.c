#include <errno.h>
#include <stdio.h>

int main() {
    int n, i;
    FILE* in = fopen("input.txt", "r");
    fscanf(in, "%d", &n);
    fclose(in);

    FILE* out = fopen("output.txt", "w");

    for(i = 0; i < 1025; i++) {
        char outname[32];
        sprintf(outname, "out_%d.txt", i);
        FILE* f = fopen(outname, "w");
        if(!f && errno == EDQUOT) {
            break;
        }
        if(f) fclose(f);
    }

    if (i >= 1000 && i < 1025) {
        fprintf(out, "correct %d\n", n);
        return 0;
    } else {
        fprintf(out, "incorrect %d\n", n);
        return 0;
    }
}
