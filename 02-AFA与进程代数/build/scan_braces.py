# -*- coding: utf-8 -*-
import re, glob, os

for f in glob.glob(r"D:\AI\AFARules\book\*.md"):
    s = open(f, encoding="utf-8").read()
    hits = []
    for m in re.finditer(r"\$([^$]*)\$", s):
        math = m.group(1)
        for i, ch in enumerate(math):
            if ch in "{}" and (i == 0 or math[i - 1] != "\\"):
                # ignore sub/superscript groups
                if i > 0 and math[i - 1] in "_^":
                    continue
                hits.append(math[max(0, i - 25):i + 25])
    if hits:
        print(os.path.basename(f), len(hits))
        for h in hits[:6]:
            print("   ", h.replace("\n", " "))
