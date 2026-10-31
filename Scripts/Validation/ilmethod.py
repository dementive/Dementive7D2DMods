"""Print IL for Class::Method from an ildasm dump, trimmed to the interesting lines.
Usage: python ilmethod.py game.il Class::Method [Class::Method ...]
"""
import re
import sys

text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
for target in sys.argv[2:]:
    marker = "// end of method " + target
    end = 0
    found = False
    while True:
        e = text.find(marker, end)
        if e < 0:
            break
        found = True
        s = text.rfind(".method ", 0, e)
        body = text[s:e]
        lines = []
        for ln in body.splitlines():
            ln = ln.strip()
            if not ln or ln.startswith(".maxstack") or ln.startswith("// Code size"):
                continue
            ln = re.sub(r"^IL_[0-9a-f]+:\s+", "", ln)
            lines.append(ln)
        print("=" * 20, target)
        print("\n".join(lines))
        end = e + len(marker)
    if not found:
        print("=" * 20, target, "NOT FOUND")
