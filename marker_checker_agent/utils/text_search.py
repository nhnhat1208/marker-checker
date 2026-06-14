from __future__ import annotations

import re
from difflib import SequenceMatcher


def _tokenize(text: str) -> list[str]:
    return re.split(r"[-_\s]+", text)


def target_match_score(query: str, target: str) -> float:
    """Return a match score in [0, 1]. 0 means no match."""
    # 1. Exact substring — highest confidence
    if query in target:
        return 1.0

    # 2. Normalized: treat -/_/space as the same character
    norm_query = re.sub(r"[-_\s]+", "", query)
    norm_target = re.sub(r"[-_\s]+", "", target)
    if norm_query and norm_query in norm_target:
        return 0.95

    # 3. Token overlap: any query token fully matches any target token
    q_tokens = _tokenize(query)
    t_tokens = _tokenize(target)
    if any(qt in t_tokens for qt in q_tokens if len(qt) >= 2):
        return 0.85

    # 4. Partial token prefix: any query token is a prefix of a target token (≥3 chars)
    if any(
        tt.startswith(qt)
        for qt in q_tokens
        for tt in t_tokens
        if len(qt) >= 3
    ):
        return 0.7

    # 5. Abbreviation / subsequence: all query chars appear in order in norm_target (≥3 chars)
    if len(norm_query) >= 3 and _is_subsequence(norm_query, norm_target):
        return 0.6

    # 6. Fuzzy ratio via difflib — handles typos
    ratio = SequenceMatcher(None, query, target).ratio()
    if ratio >= 0.7:
        return round(ratio * 0.65, 3)

    return 0.0


def _is_subsequence(query: str, target: str) -> bool:
    it = iter(target)
    return all(c in it for c in query)
