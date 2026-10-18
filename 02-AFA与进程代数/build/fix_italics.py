# -*- coding: utf-8 -*-
import re, sys

path = sys.argv[1]
s = open(path, encoding="utf-8").read()
s2 = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"**\1**", s)
open(path, "w", encoding="utf-8").write(s2)
print("replaced", s.count("*") - s2.count("*"), "asterisks")
