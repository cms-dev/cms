#include <assert.h>
#include <stdio.h>

#include "first.h"
#include "second.h"

void first_step(char *fifo_name) {
    // Open communication with second step.
    FILE *fifo = fopen(fifo_name, "w");
    // Read input.
    int n;
    scanf("%d", &n);
    // Call the user function to compute the message.
    int message = userfunc1(n);
    // Write to the second step.
    fprintf(fifo, "%d\n", message);
}

void second_step(char *fifo_name) {
    // Open communication with first step.
    FILE *fifo = fopen(fifo_name, "r");
    // Read message
    int message;
    fscanf(fifo, "%d", &message);
    // Call the user function to compute the output.
    int output = userfunc2(message);
    // Write output.
    printf("%d\n", output);
}

int main(int argc, char **argv) {
    // 0 if first step, 1 if second step.
    int step = argv[1][0] - '0';

    if (step == 0) {
        first_step(argv[2]);
    } else {
        second_step(argv[2]);
    }
    return 0;
}
