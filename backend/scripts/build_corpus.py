"""Build the Hebrew name corpus used to fit and serve name embeddings, plus
a supplementary per-year breakdown used only for the year-range filter.

Downloads two files from babynamesIL (CC0, wraps official Israel CBS
Release 391/2025 data) at a pinned commit:

1. `babynamesIL_totals.csv` -> name_corpus.csv: one row per (name, sex,
   sector), lifetime totals. This is the FULL corpus -- every name the app
   knows about, what embeddings are fit on, what autocomplete searches.
   Threshold: any name given to >=5 children in a year/sector/sex combo,
   summed across all years.
2. `babynamesIL.csv` -> name_years.csv: one row per (name, sex, sector,
   year). A SUBSET of the corpus above -- only ~5,700 of the ~19,900 names
   meet this file's stricter threshold (>=5 children in a SINGLE year, not
   summed across years). This is deliberately kept separate rather than
   used as the primary source: switching to it entirely would silently
   drop 71% of the corpus. It's supplementary data for the year-range
   filter only -- names without a yearly breakdown here simply can't be
   matched against a restricted year range (see corpus/loader.py), but
   remain fully searchable when no year filter is applied.

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
SOURCE_BASE = f"https://raw.githubusercontent.com/aviezerl/babynamesIL/{SOURCE_COMMIT}/data-raw"
TOTALS_URL = f"{SOURCE_BASE}/babynamesIL_totals.csv"
YEARLY_URL = f"{SOURCE_BASE}/babynamesIL.csv"

ARTIFACTS_DIR = Path(__file__).parent.parent / "src" / "nameme" / "artifacts"
CORPUS_OUTPUT_PATH = ARTIFACTS_DIR / "name_corpus.csv"
YEARS_OUTPUT_PATH = ARTIFACTS_DIR / "name_years.csv"

# Hebrew letters (base block + final forms). Names must consist solely of
# these characters (and internal spaces/hyphens for compound names) to be
# kept -- this filters out encoding artifacts / non-Hebrew entries.
HEBREW_NAME_RE = re.compile(r"^[א-ת][א-ת \-'\"]*$")

# The 4 sector values actually present in the source data, confirmed by
# inspection -- kept here as a sanity-check list, not a filter.
KNOWN_SECTORS = {"Jewish", "Muslim", "Christian-Arab", "Druze"}


def _clean_names(df: pd.DataFrame) -> pd.DataFrame:
    valid_name = df["name"].astype(str).str.strip().str.match(HEBREW_NAME_RE)
    dropped = df.loc[~valid_name, "name"].unique()
    if len(dropped):
        print(f"Dropping {len(dropped)} non-Hebrew-script name(s): {list(dropped)[:10]}")
    df = df.loc[valid_name].copy()
    df["name"] = df["name"].str.strip()

    unknown_sectors = set(df["sector"].unique()) - KNOWN_SECTORS
    if unknown_sectors:
        print(f"NOTE: source has sector value(s) not in KNOWN_SECTORS: {unknown_sectors}")
    return df


def _build_corpus(status: PipelineStatus) -> pd.DataFrame:
    status.step("fetching CBS/babynamesIL totals CSV")
    print(f"Fetching {TOTALS_URL}")
    raw = pd.read_csv(TOTALS_URL)
    print(f"Loaded {len(raw)} rows (sector x sex x name)")

    status.step("filtering + building corpus")
    raw = _clean_names(raw)

    # One row per (name, sex, sector) -- sector is kept (not aggregated away)
    # so the app can filter by it (e.g. "Jewish boys", "Muslim girls"). A
    # given name/sex can legitimately have rows in multiple sectors.
    corpus = (
        raw.groupby(["name", "sex", "sector"], as_index=False)["total"]
        .sum()
        .sort_values("total", ascending=False)
        .reset_index(drop=True)
    )

    n_unique = corpus["name"].nunique()
    print(f"Kept {len(corpus)} (name, sex, sector) rows across {n_unique} unique names")

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    corpus.to_csv(CORPUS_OUTPUT_PATH, index=False)
    print(f"Wrote {CORPUS_OUTPUT_PATH}")

    print("\nSanity check -- top 10 (name, sex, sector) rows by total:")
    print(corpus.head(10).to_string(index=False))

    for expected in ["שרה", "דוד", "יוסף"]:
        if expected in corpus["name"].values:
            print(f"  OK: found expected name {expected!r}")
        else:
            print(f"  WARNING: expected name {expected!r} not found in corpus")

    return corpus


def _build_year_breakdown(status: PipelineStatus, corpus_names: set[str]) -> None:
    status.step("fetching CBS/babynamesIL yearly CSV")
    print(f"\nFetching {YEARLY_URL}")
    raw = pd.read_csv(YEARLY_URL)
    print(f"Loaded {len(raw)} rows (sector x year x sex x name)")

    status.step("filtering + building year breakdown")
    raw = _clean_names(raw)

    years = (
        raw.rename(columns={"n": "total"})
        .groupby(["name", "sex", "sector", "year"], as_index=False)["total"]
        .sum()
        .sort_values(["name", "year"])
        .reset_index(drop=True)
    )

    coverage = years["name"].nunique()
    missing = len(corpus_names - set(years["name"]))
    year_lo, year_hi = years["year"].min(), years["year"].max()
    print(
        f"Kept {len(years)} (name, sex, sector, year) rows, years {year_lo}-{year_hi}. "
        f"Covers {coverage}/{len(corpus_names)} corpus names ({missing} names have no "
        "yearly breakdown -- they cleared the lifetime threshold but never the stricter "
        "single-year threshold this file uses; they stay fully searchable, just excluded "
        "when a year-range filter narrower than the full range is applied)."
    )

    years.to_csv(YEARS_OUTPUT_PATH, index=False)
    print(f"Wrote {YEARS_OUTPUT_PATH}")


def main() -> None:
    status = PipelineStatus("build_corpus")
    corpus = _build_corpus(status)
    _build_year_breakdown(status, set(corpus["name"]))
    status.done()


if __name__ == "__main__":
    main()
