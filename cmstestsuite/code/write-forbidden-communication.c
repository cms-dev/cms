#include <stdio.h>

int userfunc(int x) {
    FILE *out = fopen("output.txt", "w");
    FILE *other = fopen("other.txt", "w");
    if (out != NULL ||other != NULL) {
        return x;
    }
    return -1;
}
