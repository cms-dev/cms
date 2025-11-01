import sys

import communication  # Submission format is ["communication.%l"]

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
    fout.write("correct %d\n" % communication.userfunc(n))
    fout.flush()
