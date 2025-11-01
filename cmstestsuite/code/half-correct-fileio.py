n = int(open("input.txt").readline().strip())
f = open("output.txt", "w")
if n % 2 == 0:
    f.write("correct 0\n")
else:
    f.write("correct %d\n" % n)
