#include <iostream>

int main() {
    int *big;
    big = new int[128 * 1024 * 1024];
    // If we don't do this cycle, the compiler is smart enough not to
    // map the array into resident memory.
    for (int i = 0; i < 128 * 1024 * 1024; i++) {
      big[i] = 0;
    }
    std::cin >> big[10000];
    std::cout << "correct " << big[10000] << std::endl;
    return 0;
}
