#include <iostream>

static_assert(__cplusplus == 201703L, "C++17 expected");

int main() {
    int n;
    std::cin >> n;
    std::cout << "correct " << n << std::endl;
}
