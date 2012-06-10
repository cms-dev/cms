#include <iostream>

int main() {
    int n;
    std::cin >> n;
    std::cout << "correct " << (n % 2 ? n : 0) << std::endl;
    return 0;
}
