# Data source

The Hebrew name corpus (`backend/src/nameme/artifacts/name_corpus.csv`) is derived from
the [`aviezerl/babynamesIL`](https://github.com/aviezerl/babynamesIL) R package, which
wraps official Israeli given-name data published by the Central Bureau of Statistics
(CBS), Release 391/2025. It covers births 1948–2024, including any name given to at least
5 children in a given year/sector/sex combination.

- **Upstream repo**: https://github.com/aviezerl/babynamesIL
- **Raw file used**: `data-raw/babynamesIL_totals.csv`
- **Pinned commit**: `63b88aac07e49a81bec5da9b9303b39439f7604c` (fetched 2026-08-18)
- **License**: CC0 (per the package `DESCRIPTION`), wrapping data released under the
  [CBS end-user license](https://www.cbs.gov.il/en/Pages/Enduser-license.aspx), which
  permits copying, redistribution, and commercial/non-commercial derivative works
  provided no endorsement by CBS/State of Israel is implied.
- **Attribution** (courtesy, not a legal requirement under CC0): data originates from the
  Israel Central Bureau of Statistics, Release 391/2025, via the `babynamesIL` R package
  by Avi Ezer-El.

## How the corpus was built

`backend/scripts/build_corpus.py` downloads the totals CSV from the pinned commit above,
aggregates it to one row per `(name, sex)` pair (summing counts across sector), drops a
small number of non-Hebrew-script entries (encoding artifacts), and writes the result to
`backend/src/nameme/artifacts/name_corpus.csv`. Result: 22,270 unique (name, sex) rows.

## Refreshing the data

This is a manual, occasional step — not an automated pipeline. To refresh:
1. Check https://github.com/aviezerl/babynamesIL for a newer CBS release.
2. Update `SOURCE_COMMIT` in `backend/scripts/build_corpus.py` to the new commit SHA.
3. Re-run `uv run python scripts/build_corpus.py` from `backend/`.
4. Re-run `uv run python scripts/build_artifacts.py` to refit the embedder/PCA on the
   updated corpus.
5. Update the pinned commit and fetch date in this file.

## Known limitation

The corpus is a point-in-time snapshot (through 2024) with no automatic refresh — this is
an accepted trade-off for a portfolio MVP.
