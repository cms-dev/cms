import sys

big = [0] * (125 * 1000 * 1000)
big[10000] = int(sys.stdin.readline().strip())
sys.stdout.write("correct %d\n" % big[10000])
