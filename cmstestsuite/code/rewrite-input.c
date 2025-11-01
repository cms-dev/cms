#include <stdio.h>

/*
 * This returns the wrong result, but overwrites the input file so
 * that a wrong result appears as a correct one. CMS is expected not
 * to be fooled by this cheat attempt.
 *
 * CMS can counter this attack by making input.txt not writable or by
 * rewriting it again before calling the checker. Both things should
 * happen at the moment. This test is here to check that at least one
 * is functional.
 */

int userfunc(int x) {
    FILE *fin = fopen("input.txt", "w");
    fprintf(fin, "%d\n", x+1);
    fclose(fin);
    return x+1;
}
