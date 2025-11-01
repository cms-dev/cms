#include <stdio.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>

int main() {
    int n;

    pid_t ret = fork();

    // Continue computation only in the child process
    if (ret == 0) {
      scanf("%d", &n);
      printf("correct %d\n", n);
    } else {
      if (ret != -1) {
        waitpid(ret, NULL, 0);
      }
    }

    return 0;
}
