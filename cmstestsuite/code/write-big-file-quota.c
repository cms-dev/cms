
#include <errno.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main() {
    int n, i;
    FILE* in = fopen("input.txt", "r");
    fscanf(in, "%d", &n);

    FILE* temp = fopen("temp.txt", "w");
    // The quota is set to 64MB, so this should fail.
    int size = 65*1024*1024;
    char* buf = calloc(size, 1);
    size_t res = fwrite(buf, 1, size, temp);
    int write_error = errno;
    fclose(temp);
    // Clean up the temporary file, so that we have space for output.txt
    unlink("temp.txt");
    FILE* out = fopen("output.txt", "w");

    if (res < size && write_error == EDQUOT) {
        fprintf(out, "correct %d\n", n);
        return 0;
    } else {
        fprintf(out, "incorrect %d\n%d", n, write_error);
        return 0;
    }
}
