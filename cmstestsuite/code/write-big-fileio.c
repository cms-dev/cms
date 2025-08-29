#include <stdio.h>

#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>

/* First we create a huge file in output.txt (2 GB). If the check on
   file size is enforced, the write fails and we write a wrong
   output. Otherwise we write correct output.

   Note that since the file is sparse, it doesn't use up much real disk
   space, and thus won't hit the disk quota (if that is configured).
   */

int main() {
    int n, i;
    FILE *in = fopen("input.txt", "r");
    fscanf(in, "%d", &n);

    // Seek is done in two steps so there are no probles even when
    // type off_t is 4 bytes long. In this part everything is done
    // calling directly syscalls because apparently libc does not
    // properly report EFBIG errors.
    int outfd = open("output.txt", O_WRONLY|O_CREAT|O_TRUNC, 0666);
    lseek(outfd, 1024 * 1024 * 1024, SEEK_CUR);
    lseek(outfd, 1024 * 1024 * 1024, SEEK_CUR);
    i = write(outfd, "\0", 1);
    close(outfd);

    FILE *out = fopen("output.txt", "w");
    if (i != 1) {
        fprintf(out, "incorrect %d\n", n);
        return 1;
    } else {
        fprintf(out, "correct %d\n", n);
        return 0;
    }
}
