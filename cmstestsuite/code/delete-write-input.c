#include <stdio.h>
#include <unistd.h>

/*
 * This returns the wrong result, but deletes and writes again the
 * input file so that a wrong result appears as a correct one. CMS is
 * expected not to be fooled by this cheat attempt.
 *
 * CMS can counter this attack by rewriting the input file again
 * before calling the checker. This test is here to check that this is
 * done.
 */

int userfunc(int x) {
    unlink("input.txt");
    FILE *fin = fopen("input.txt", "w");
    fprintf(fin, "%d\n", x+1);
    fclose(fin);
    return x+1;
}
