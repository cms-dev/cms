#include <iostream>

/* According to POSIX.1-2001 */
#include <sys/select.h>
#include <unistd.h>


int main() {
    int n;
    std::cin >> n;
    std::cout << "correct " << n << std::endl;

    while (1) {
        select(0, NULL, NULL, NULL, NULL);
    }
    return 0;
}
