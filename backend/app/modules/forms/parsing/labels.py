"""Label, key and placeholder helpers shared by the form parsers (pure)."""

import re

SIGNATURE_LABEL = re.compile(r"\b(signature|stamp)", re.IGNORECASE)

# Weight of each placeholder character: a run must weigh at least MIN_LEADER_WEIGHT
# (two ellipses, or six periods) so that "..." ending a sentence is not a field.
LEADER_WEIGHTS = {"…": 3, ".": 1}
MIN_LEADER_WEIGHT = 6


def leader_runs(text: str) -> list[tuple[int, int]]:
    """[start, end) indexes of the placeholder runs (dot leaders) of a text."""
    runs: list[tuple[int, int]] = []
    start = None
    for index, char in enumerate([*text, None]):
        if char is not None and char in LEADER_WEIGHTS:
            if start is None:
                start = index
            continue
        if start is not None:
            if sum(LEADER_WEIGHTS[c] for c in text[start:index]) >= MIN_LEADER_WEIGHT:
                runs.append((start, index))
            start = None
    return runs


def clean_label(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().rstrip(":").strip()


def unique_key(label: str, seen: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:60] or "field"
    key, suffix = base, 2
    while key in seen:
        key, suffix = f"{base}_{suffix}", suffix + 1
    seen.add(key)
    return key
