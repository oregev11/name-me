"""Fetches a large general-Hebrew word list used to fit written_similarity's
TF-IDF vectorizer against real Hebrew usage, instead of only against the
~20K given names it serves (see NgramSvdEmbedder.fit_corpus).

Source: eyaler/hebrew_wordlists' `hspell_simple.txt` -- ~130K individual
Hebrew word forms derived from the Hspell 1.4 dictionary, one word per line
(the same "one word = one document" granularity as our name corpus, which
is what makes it a meaningful drop-in background corpus for IDF fitting).

Not committed to the repo (fetched fresh at build_artifacts.py run time,
same pattern as build_corpus.py's CBS data fetch) -- see DATA_SOURCE.md for
license details (AGPL v3) and why that's fine for this use (deriving
statistics from the corpus, not redistributing it).
"""

from __future__ import annotations

import urllib.request

SOURCE_COMMIT = "1e5776ff0a25ad5aac1a595486ba284cf89ebefa"
SOURCE_URL = (
    "https://raw.githubusercontent.com/eyaler/hebrew_wordlists/"
    f"{SOURCE_COMMIT}/hspell_simple.txt"
)


def fetch_background_corpus() -> list[str]:
    with urllib.request.urlopen(SOURCE_URL, timeout=60) as resp:  # noqa: S310
        text = resp.read().decode("utf-8")
    words = [w.strip() for w in text.splitlines() if w.strip()]
    return words
