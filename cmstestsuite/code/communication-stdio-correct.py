import sys

while True:
    n = sys.stdin.readline().strip()
    if n == "":
        # EOF, let's quit.
        break

    n = int(n)
    if n == 0:
        break
    sys.stdout.write("correct %d\n" % n)
    sys.stdout.flush()
