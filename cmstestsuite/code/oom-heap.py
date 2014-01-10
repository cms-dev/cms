import sys

big = [0] * (128 * 1024 * 1024)
big[10000] = int(sys.stdin.readline().strip())
sys.stdout.write("correct %d\n" % big[10000])
