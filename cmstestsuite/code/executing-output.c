#include <stdio.h>
#include <errno.h>
#include <unistd.h>

extern int errno;

// This solution is correct only if it cannot execute output.txt (as
// it shouldn't be able to).
int main() {
    int n;

    // Reading the input number.
    FILE *in = fopen("input.txt", "r");
    fscanf(in, "%d", &n);

    // Writing the head of an ELF file on  output.
    FILE *out = fopen("output.txt", "w");
    fprintf(out, "\x7F\x45\x4c\x46\x01\x01\x01");
    fclose(out);

    // Trying executing the output.
    execl("output.txt", "output.txt", NULL);

    // If the execution was denied because of permissions (as it
    // should), write the correct output.
    if (errno == EACCES) {
      out = fopen("output.txt", "w");
      fprintf(out, "correct %d\n", n);
    }
    return 0;
}
