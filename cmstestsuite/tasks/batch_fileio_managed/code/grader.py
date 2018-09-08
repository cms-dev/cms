import batchfileiomanaged

n = int(open("input.txt").readline().strip())
f = open("output.txt", "w")
f.write("correct %d\n" % batchfileiomanaged.userfunc(n))
# f intentionally left open.
