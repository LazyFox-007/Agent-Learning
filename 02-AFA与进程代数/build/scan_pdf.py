# -*- coding: utf-8 -*-
import sys, re
import pymupdf

pdf = sys.argv[1]
doc = pymupdf.open(pdf)
print("pages", doc.page_count)
for i, page in enumerate(doc):
    t = page.get_text()
    bad = re.findall(r"\\[A-Za-z]{2,}", t)
    if bad:
        print("PAGE", i + 1, "raw-latex", sorted(set(bad))[:8])
    if "□" in t:
        print("PAGE", i + 1, "tofu-box")
    for ch in ["第 7 章", "第 8 章", "第 9 章", "第 6 章"]:
        if ch in t and ("导论" not in t):
            print("PAGE", i + 1, "contains", ch)
