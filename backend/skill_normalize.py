"""Slugify and normalize skill strings before DB / Prolog."""

import re
from typing import List


def normalize_display(s: str) -> str:
    if not s or not isinstance(s, str):
        return ""
    t = s.strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def strip_parenthetical_versions(s: str) -> str:
    """Remove parenthetical segments often used for versions or tools, e.g. (v18), (AWS)."""
    if not s:
        return ""
    out = re.sub(r"\([^)]*\)", " ", s)
    return re.sub(r"\s+", " ", out).strip()


def to_slug(s: str) -> str:
    """
    Lowercase, strip parentheticals, then slug.

    Keeps common language-style characters: ``+`` ``#`` ``.`` ``-`` (e.g. c++, c#, f#,
    node.js, asp.net, foo-bar). Whitespace and other punctuation become underscores;
    underscore runs are collapsed and trimmed from the ends.
    """
    base = strip_parenthetical_versions(normalize_display(s))
    if not base:
        return ""
    base = base.strip()
    base = re.sub(r"\s+", "_", base)
    # Allow a-z, 0-9, _, #, ., +, - (hyphen must be last in the class to be literal)
    slug = re.sub(r"[^a-z0-9_#.+_-]+", "_", base)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug


def normalize_skill_list(raw: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        sl = to_slug(item)
        if sl and sl not in seen:
            seen.add(sl)
            out.append(sl)
    return out
