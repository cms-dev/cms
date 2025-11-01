import sys

import user1
import user2


while True:
    n = sys.stdin.readline().strip()
    if n == "":
        # EOF, let's quit.
        break

    n = int(n)
    if n == 0:
        break
    if int(sys.argv[1]) == 0:
        sys.stdout.write("correct %d\n" % user1.userfunc1(n))
    else:
        sys.stdout.write("correct %d\n" % user2.userfunc2(n))
    sys.stdout.flush()
