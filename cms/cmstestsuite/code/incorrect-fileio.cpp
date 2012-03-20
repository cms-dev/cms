#include <fstream>

int main() {
    int n;
    std::ifstream in("input.txt");
    std::ofstream out("output.txt");
    in >> n;
    out << "incorrect " << n << std::endl;
    return 0;
}
