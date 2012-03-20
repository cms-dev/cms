#include <iostream>
#include <time.h>

int main() {
    int n;
    std::cin >> n;
    std::cout << "correct " << n << std::endl;
    while (1) {
        struct timespec ts;
        ts.tv_sec = 1000;
        ts.tv_nsec = 0;
        nanosleep(&ts, NULL);
    }
    return 0;
}
