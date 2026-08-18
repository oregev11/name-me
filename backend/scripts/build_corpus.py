"""Build the Hebrew name corpus used to fit and serve name embeddings.

Downloads the babynamesIL "totals" dataset (CC0, wraps official Israel CBS
Release 391/2025 data) from a pinned commit on GitHub, aggregates it to one
row per (name, sex), filters out non-Hebrew-script anomalies, and writes the
result to backend/src/nameme/artifacts/name_corpus.csv.

This is a one-time / occasional-refresh offline step. Its output is committed
to the repo so the backend never depends on this third-party URL at runtime.

Usage:
    uv run python scripts/build_corpus.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from pipeline_status import PipelineStatus

# Pinned to a specific commit (not `main`) so this script is reproducible even
# if the upstream repo changes format later. See DATA_SOURCE.md for the date
# this was pinned and how to refresh it.
SOURCE_COMMIT = "63b88aac07e49a81bec5da9b9303b39439f7604c"
SOURCE_URL = (
    "https://raw.githubusercontent.com/aviezerl/babynamesIL/"
    f"{SOURCE_COMMIT}/data-raw/babynamesIL_totals.csv"
)

OUTPUT_PATH = Path(__file__).parent.parent / "src" / "nameme" / "artifacts" / "name_corpus.csv"

# Hebrew letters (base block + final forms). Names must consist solely of
# these characters (and internal spaces/hyphens for compound names) to be
# kept -- this filters out encoding artifacts / non-Hebrew entries.
HEBREW_NAME_RE = re.compile(r"^[א-ת][א-ת \-'\"]*$")


def main() -> None:
    status = PipelineStatus("build_corpus")
    status.step("fetching CBS/babynamesIL CSV")
    print(f"Fetching {SOURCE_URL}")
    raw = pd.read_csv(SOURCE_URL)
    print(f"Loaded {len(raw)} rows (sector x sex x name)")

    status.step("filtering + aggregating")
    valid_name = raw["name"].astype(str).str.strip().str.match(HEBREW_NAME_RE)
    dropped = raw.loc[~valid_name, "name"].unique()
    if len(dropped):
        print(f"Dropping {len(dropped)} non-Hebrew-script name(s): {list(dropped)[:10]}")
    raw = raw.loc[valid_name].copy()
    raw["name"] = raw["name"].str.strip()

    # Aggregate across sector: one row per (name, sex) with summed total.
    # Names used for both sexes are kept as two separate rows -- sex is
    # metadata attached to spelling, not something we collapse away.
    corpus = (
        raw.groupby(["name", "sex"], as_index=False)["total"]
        .sum()
        .sort_values("total", ascending=False)
        .reset_index(drop=True)
    )

    print(f"Aggregated to {len(corpus)} unique (name, sex) rows")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    corpus.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {OUTPUT_PATH}")

    print("\nSanity check -- top 10 names by total:")
    print(corpus.head(10).to_string(index=False))

    for expected in ["שרה", "דוד", "יוסף"]:
        if expected in corpus["name"].values:
            print(f"  OK: found expected name {expected!r}")
        else:
            print(f"  WARNING: expected name {expected!r} not found in corpus")

    status.done()


if __name__ == "__main__":
    main()
