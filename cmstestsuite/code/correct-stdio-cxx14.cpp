#include <iostream>

static_assert(__cplusplus == 201402L, "C++14 expected");

int main() {
    int n;
    std::cin >> n;
    std::cout << "correct " << n << std::endl;
}
