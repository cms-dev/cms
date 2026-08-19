import sys

import user1
import user2


fin = open(sys.argv[1], "r")
fout = open(sys.argv[2], "w")

while True:
    n = fin.readline().strip()
    if n == "":
        # EOF, let's quit.
        break

    n = int(n)
    if n == 0:
        break
    if int(sys.argv[3]) == 0:
        fout.write("correct %d\n" % user1.userfunc1(n))
    else:
        fout.write("correct %d\n" % user2.userfunc2(n))
    fout.flush()
