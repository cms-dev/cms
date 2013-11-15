import sys

n = int(sys.stdin.readline().strip())
if n % 2 == 0:
    sys.stdout.write("correct 0\n")
else:
    sys.stdout.write("correct %d\n" % n)
