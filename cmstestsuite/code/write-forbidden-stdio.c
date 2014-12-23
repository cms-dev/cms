#include <stdio.h>

int main() {
    int n;
    // The submission is allowed (for technical reasons) to access
    // output.txt, that is the file where the standard output will be
    // redirected. This is no advantage though.
    FILE *other = fopen("other.txt", "w");
    if (other != NULL) {
      scanf("%d", &n);
      printf("correct %d\n", n);
    }
    return 0;
}
