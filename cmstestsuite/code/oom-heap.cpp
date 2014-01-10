#include <iostream>

int main() {
    int *big;
    big = new int[128 * 1024 * 1024];
    std::cin >> big[10000];
    std::cout << "correct " << big[10000] << std::endl;
    return 0;
}
