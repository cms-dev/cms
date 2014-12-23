#include <stdio.h>

int userfunc(int x) {
    // The submission is allowed to access output.txt, that is the
    // file where the output of the grader will be written. The grader
    // should be designed in such a way that this is not an advantage.
    FILE *other = fopen("other.txt", "w");
    if (other != NULL) {
        return x;
    }
    return -1;
}
