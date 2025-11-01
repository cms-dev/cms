#include <fstream>

int main() {
    int n;
    std::ifstream in("input.txt");
    std::ofstream out("output.txt");
    in >> n;
    out << "correct " << (n % 2 ? n : 0) << std::endl;
    return 0;
}
