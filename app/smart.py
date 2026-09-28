"""Smart search: Cyrillic and Latin spellings of the same name match («Бухоро» = «Buxoro» = «BUKHORO»).

norm() transliterates Cyrillic (Uzbek/Russian) to Latin, lower-cases and drops apostrophes, quotes, spaces and
punctuation, so a query typed in either alphabet finds names written in the other. The same table lives in app.js.
"""
from __future__ import annotations
import re

_CYR = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh",
        "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya", "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h"}
_LAT = (("kh", "x"), ("’", ""), ("'", ""), ("`", ""), ("ʻ", ""), ("ʼ", ""))

def norm(s) -> str:
    t = str(s or "").lower()
    t = "".join(_CYR.get(ch, ch) for ch in t)
    for a, b in _LAT: t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "", t)

def match(query, *fields) -> bool:
    """True when every word of the query is found (normalized) in the normalized fields joined together."""
    words = [norm(w) for w in str(query or "").split()]
    words = [w for w in words if w]
    if not words: return True
    hay = " ".join(norm(f) for f in fields if f)
    return all(w in hay for w in words)
