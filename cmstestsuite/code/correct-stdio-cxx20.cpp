#include <iostream>

static_assert(__cplusplus == 202002L, "C++20 expected");

int main() {
    int n;
    std::cin >> n;
    std::cout << "correct " << n << std::endl;
}
