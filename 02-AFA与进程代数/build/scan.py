import re, glob, collections, os
root = r"D:\AI\AFARules\book"
cmds = collections.Counter()
files = glob.glob(os.path.join(root, "*.md"))
print("files:", len(files))
for f in files:
    s = open(f, encoding="utf-8").read()
    for m in re.finditer(r"\\([A-Za-z]+)", s):
        cmds[m.group(1)] += 1
for k, v in sorted(cmds.items()):
    print("%-22s %d" % (k, v))
