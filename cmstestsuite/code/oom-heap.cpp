#include <iostream>

int main() {
    int *big;
    big = new int[64 * 1024 * 1024];
    std::cin >> big[10000];
    std::cout << "correct " << big[10000] << std::endl;
    return 0;
}
