#include <iostream>
#include <signal.h>

int main() {
    int n;
    std::cin >> n;
    std::cout << "correct " << n << std::endl;
    while (1) {
        raise(SIGSTOP);
    }
    return 0;
}
