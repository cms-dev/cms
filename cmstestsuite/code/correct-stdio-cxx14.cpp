#include <iostream>
#include <memory>

// Test C++14 support

int main() {
    auto ptr = std::make_unique<int>();
    std::cin >> *ptr;
    std::cout << "correct " << *ptr << std::endl;
    return 0b0'0'0;
}
