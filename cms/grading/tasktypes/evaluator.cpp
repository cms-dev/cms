#include <iostream>
#include <unistd.h>
#include <string>
#include <cstdio>
#include <cctype>
#include <fstream>
#include <functional>
#include <sstream>
#include <cstring>


#include <sys/types.h>
#include <fcntl.h>
#include <cstdlib>

#define READ 0
#define WRITE 1

pid_t popen2(const char *command, int *infp, int *outfp) {
    int p_stdin[2], p_stdout[2];
    pid_t pid;

    if (pipe(p_stdin) != 0 || pipe(p_stdout) != 0)
        return -1;

    pid = fork();

    if (pid < 0)
        return pid;
    else if (pid == 0)
    {
        close(p_stdin[WRITE]);
        dup2(p_stdin[READ], READ);
        close(p_stdout[READ]);
        dup2(p_stdout[WRITE], WRITE);
        close(p_stdout[READ]);
        close(p_stdin[WRITE]);

        execl("/bin/sh", "sh", "-c", command, NULL);
        perror("execl");
        exit(1);
    }

    if (infp == NULL)
        close(p_stdin[WRITE]);
    else
        *infp = p_stdin[WRITE];

    if (outfp == NULL)
        close(p_stdout[READ]);
    else
        *outfp = p_stdout[READ];

    close(p_stdin[READ]);
    close(p_stdout[WRITE]);
    return pid;
}


// Returns true if a differs from b, false otherwise
// Ignore the 'input' file.
bool whiteDiff(std::string a, std::string b, std::string _) {
    int i = 0, j = 0;
    for (;;i++,j++) {
        while (i < a.size() && isspace(a[i])) i++;
        while (j < b.size() && isspace(b[j])) j++;
        // if i is at the end and j is not, b has extra stuff.
        // if j is at the end and i is not, a has extra stuff
        // if a[i] and b[i] are not equal, they're not equal
        if (i == a.size() && j == b.size())
            return false;
        if ((i == a.size() && j != b.size()) ||
            (i != a.size() && j == b.size()) ||
            a[i] != b[i])
            return true;
    }

}

int infp, outfp;

std::string exec(auto cmd, std::string data="") {
    auto pipe = popen2(cmd.c_str(), &infp, &outfp);
    if (!pipe) return "Couldn't create pipe to " + cmd;
    auto result = std::string("");
    if (data != "") {
        write (infp, data.c_str(), data.size() + 1);
    }
    char buffer[128];
    int numread = 1;
    while (numread != 0) {
        memset(buffer, 0, 128);
        if ((numread = read(outfp, buffer, 128)) > 0) {
            result += buffer;
        }
    }
    close(infp);
    close(outfp);
    return result;
}

bool customChecker(std::string exeName, std::string programOut, std::string studentOut, std::string studentIn) {
    auto out = exec(exeName + " " + studentIn, programOut + "\n" + studentOut);
    return std::stoi(out);
}


int main(int argc, char* argv[]) {
    if (argc != 6 && argc != 7) {
        std::cerr << "Invalid number of arguments. Expecting " << argv[0] <<
                     " input.txt output.txt <sanity> <correct> <incorrect> <?evaluator>" <<
                     std::endl;
        return 1;
    }

    std::ifstream inp(argv[2]);
    inp.seekg(0, std::ios::end);
    size_t size = inp.tellg();
    std::string outputText(size, ' ');
    inp.seekg(0);
    inp.read(&outputText[0], size);
    std::function<bool(std::string, std::string, std::string)> checker = whiteDiff;
    if (argc == 7) {
        checker = std::bind(customChecker, "./" + std::string(argv[6]), std::placeholders::_1, std::placeholders::_2, std::placeholders::_3);
    }

    /* Check that sanity, correct and incorrect are binary files that we can
     * execute */
    if (access(argv[3], X_OK)) {
        std::cerr << argv[3] << " is not executable." << std::endl;
        return 1;
    }
    if (access(argv[4], X_OK)) {
        std::cerr << argv[4] << " is not executable." << std::endl;
        return 1;
    }
    if (access(argv[5], X_OK)) {
        std::cerr << argv[5] << " is not executable." << std::endl;
        return 1;
    }

    auto isSane = exec("./" + std::string(argv[3]) + " " + std::string(argv[1]));
    if (std::stoi(isSane) != 1) {
        std::cout << "-3" << std::endl;
        std::cerr << "Test case was insane" << std::endl;
        return 0;
    }

    auto producesOutput = checker(exec("./" + std::string(argv[4]) + " < " + std::string(argv[1])), outputText, argv[1]) == false;
    if (!producesOutput) {
        std::cout << "-2" << std::endl;
        std::cerr << "The input file does not produce the output file" << std::endl;
        return 0;
    }

    auto breaks = checker(exec("./" + std::string(argv[5]) + " < " + std::string(argv[1])), outputText, argv[1]);
    if (!breaks) {
        std::cout << "-1" << std::endl;
        std::cerr << "The input file does not break this code" << std::endl;
        return 0;
    }
    std::cout << "1" << std::endl;
    std::cout << "You have successfully broken this code" << std::endl;
    return 0;
}
