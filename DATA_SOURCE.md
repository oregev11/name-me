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

`backend/scripts/build_corpus.py` downloads **two** files from the pinned commit above and
writes two outputs:

1. **`data-raw/babynamesIL_totals.csv`** (lifetime totals, threshold: ≥5 children in a
   year/sector/sex combo, summed across all years) → `name_corpus.csv` — the FULL corpus:
   one row per `(name, sex, sector)`. **sector** is CBS's population-group breakdown
   (Jewish / Muslim / Christian-Arab / Druze, the "tabs" the source release is organized
   by), used for the sex/sector search filters and *not* aggregated away. 28,623 rows
   across 19,882 unique names — every name the app knows about, what embeddings are fit on.
2. **`data-raw/babynamesIL.csv`** (yearly breakdown, a *stricter* threshold: ≥5 children in
   a **single** year) → `name_years.csv` — one row per `(name, sex, sector, year)`, powers
   the year-range "ruler" filter. 159,678 rows, years 1949–2024, but only **5,706 of the
   19,882 corpus names** meet this file's stricter threshold. This is deliberately kept
   separate from (1) rather than used as the primary corpus source: switching to it
   entirely would silently drop 71% of the corpus. Names without a yearly breakdown remain
   fully searchable with no year filter applied; they're excluded only when a year range
   narrower than the full 1949–2024 span is requested, since there's no evidence of which
   years they were actually given in.

Both steps drop a small number of non-Hebrew-script entries (encoding artifacts) first.

## Refreshing the data

This is a manual, occasional step — not an automated pipeline. To refresh:
1. Check https://github.com/aviezerl/babynamesIL for a newer CBS release.
2. Update `SOURCE_COMMIT` in `backend/scripts/build_corpus.py` to the new commit SHA.
3. Re-run `uv run python scripts/build_corpus.py` from `backend/` (rebuilds both
   `name_corpus.csv` and `name_years.csv`).
4. Re-run `uv run python scripts/build_artifacts.py` to refit the embedder/PCA on the
   updated corpus (only needed if `name_corpus.csv`'s name list changed).
5. Update the pinned commit and fetch date in this file.

## Known limitation

The corpus is a point-in-time snapshot (through 2024) with no automatic refresh — this is
an accepted trade-off for a portfolio MVP.

## Background Hebrew word corpus (for `written_similarity`'s IDF weighting)

`written_similarity`'s TF-IDF vectorizer fits its vocabulary and document-frequency
weighting against a large general-Hebrew word list rather than only the ~20K given names —
this judges how rare/common a given character substring really is against real Hebrew
usage, not against the biased sample of spellings that happen to be given names.

- **Source**: [`eyaler/hebrew_wordlists`](https://github.com/eyaler/hebrew_wordlists),
  file `hspell_simple.txt` — ~130K individual Hebrew word forms derived from the
  [Hspell](https://github.com/synhershko/hspell) 1.4 Hebrew spellchecker dictionary, one
  word per line.
- **Pinned commit**: `1e5776ff0a25ad5aac1a595486ba284cf89ebefa`
- **License**: Hspell's dictionary and derived word lists are licensed under **AGPL v3**
  (per `hebrew_wordlists`' `LICENSE` file). **This is intentionally NOT the same permissive
  situation as the CBS name data above** — flagging it explicitly rather than glossing over
  it: this project does not redistribute the word list itself (it's fetched fresh at
  `build_artifacts.py` run time, never committed to this repo, same pattern as the CBS
  fetch), and only derives a statistical property from it (character n-gram document
  frequencies) to fit `written_similarity`'s vectorizer — the committed artifact
  (`embedder.joblib`) reflects those statistics but contains none of the source text. This
  is a reasonable, common practice for training/fitting statistical models on a corpus, but
  is disclosed here rather than left implicit, since AGPL's copyleft terms are stricter than
  the CC0 data used elsewhere in this project.
- **Fetched by**: `backend/scripts/background_corpus.py`, used from
  `backend/scripts/build_artifacts.py`.
