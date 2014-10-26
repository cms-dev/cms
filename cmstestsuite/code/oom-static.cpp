#include <iostream>

int big[128 * 1024 * 1024 / sizeof(int)];

int main() {
    // If we don't do this cycle, the compiler is smart enough not to
    // map the array into resident memory.
    for (int i = 0; i < 128 * 1024 * 1024 / sizeof(int); i++) {
      big[i] = 0;
    }
    std::cin >> big[10000];
    std::cout << "correct " << big[10000] << std::endl;
    return 0;
}
