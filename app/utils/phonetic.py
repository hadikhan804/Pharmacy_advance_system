from __future__ import annotations

import re


def fold(text: str) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    s = re.sub(r"(.)\1+", r"\1", s)
    for a, b in (("yle", "il"), ("ol", "ol"), ("in", "in")):
        pass
    if s.endswith("e") and len(s) > 4:
        s = s[:-1]
    return s


def search_variants(query: str) -> list[str]:
    q = (query or "").strip()
    if not q:
        return []
    out = [q]
    folded = fold(q)
    if folded and folded.lower() not in {x.lower() for x in out}:
        out.append(folded)
    lower = q.lower()
    if not lower.endswith("e"):
        out.append(q + "e")
    elif len(q) > 4:
        out.append(q[:-1])
    seen: set[str] = set()
    unique: list[str] = []
    for item in out:
        key = item.lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique
