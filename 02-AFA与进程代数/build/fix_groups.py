# -*- coding: utf-8 -*-
import glob

pairs = [
    (r"{\sim}", r"\sim"),
    (r"{\approx}", r"\approx"),
    (r"{\equiv}", r"\equiv"),
    (r"{\approx^c}", r"\approx^c"),
]
for f in glob.glob(r"D:\AI\AFARules\book\*.md"):
    s = open(f, encoding="utf-8").read()
    t = s
    for a, b in pairs:
        t = t.replace(a, b)
    if t != s:
        open(f, "w", encoding="utf-8").write(t)
        print("fixed", f)
