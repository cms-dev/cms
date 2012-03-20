#include <iostream>
#include <unistd.h>

int main() {
    int n;
    std::cin >> n;
    std::cout << "correct " << n << std::endl;
    while (1) {
        pause();
    }
    return 0;
}
