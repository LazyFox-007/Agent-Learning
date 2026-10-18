# -*- coding: utf-8 -*-
import re, glob, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import tex

known = set(tex.SYMBOLS) | set(tex.GREEK) | {
    "mathrm", "mathbf", "mathbb", "mathit", "mathcal", "text", "operatorname",
    "xrightarrow", "xRightarrow", "overline", "not",
}
seen = {}
for f in glob.glob(r"D:\AI\AFARules\book\*.md"):
    s = open(f, encoding="utf-8").read()
    for m in re.finditer(r"\\([A-Za-z]+)", s):
        seen.setdefault(m.group(1), set()).add(os.path.basename(f))
for k in sorted(seen):
    if k not in known:
        print("UNKNOWN", k, "in", ", ".join(sorted(seen[k])))
print("total distinct:", len(seen))
