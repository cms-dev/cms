import sys

import communication  # Submission format is ["communication.%l"]


while True:
    n = sys.stdin.readline().strip()
    if n == "":
        # EOF, let's quit.
        break

    n = int(n)
    if n == 0:
        break
    sys.stdout.write("correct %d\n" % communication.userfunc(n))
    sys.stdout.flush()
