#include <iostream>

int big[132108864];

int main() {
    // If we don't do this cycle, the compiler is smart enough not to
    // map the array into resident memory.
    for (int i = 0; i < 132108864; i++) {
      big[i] = 0;
    }
    std::cin >> big[10000];
    std::cout << "correct " << big[10000] << std::endl;
    return 0;
}
