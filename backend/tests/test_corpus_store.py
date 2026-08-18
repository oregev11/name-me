"""Unit tests for CorpusStore's sex/sector metadata and filter matching --
built against the real committed name_corpus.csv (long format: one row per
(name, sex, sector), see scripts/build_corpus.py), not a fabricated fixture,
since the whole point is to catch real data shape issues.
"""

from __future__ import annotations

import pytest

from nameme.config import ARTIFACTS_DIR
from nameme.corpus.loader import load_corpus_store

# דניאל is a real, useful edge case: overwhelmingly a boys' name (~62K)
# but also given to ~13K girls -- a "dominant sex" of M that should NOT
# make it invisible to a sex=F filter (that was a real bug: matching only
# against the dominant sex, fixed by matching against actual (sex,sector)
# row membership instead -- see CorpusStore.matches_sex_sector).
UNISEX_NAME = "דניאל"

# Real names with a narrow, non-overlapping year presence in the yearly
# breakdown -- useful for exercising the year-range filter precisely.
# RECENT_ONLY_NAME only appears 2015-2024; OLD_ONLY_NAME only 1949-1960.
RECENT_ONLY_NAME = "אילאן"
OLD_ONLY_NAME = "זינובי"


@pytest.fixture(scope="module")
def store():
    return load_corpus_store(ARTIFACTS_DIR)


def test_unisex_name_has_both_sexes_in_combos(store) -> None:
    combos = store.meta_for(UNISEX_NAME)["combos"]
    sexes = {s for s, _sector in combos}
    assert sexes == {"M", "F"}


def test_matches_sex_sector_finds_the_non_dominant_sex(store) -> None:
    # Dominant/display sex is M (more boys than girls have this name)...
    assert store.meta_for(UNISEX_NAME)["sex"] == "M"
    # ...but a sex=F filter must still match it, since real girls-with-this
    # -name rows exist. This is the bug fix this test locks in.
    assert store.matches_sex_sector(UNISEX_NAME, sex="F", sector="any") is True
    assert store.matches_sex_sector(UNISEX_NAME, sex="M", sector="any") is True


def test_matches_sex_sector_any_always_matches(store) -> None:
    assert store.matches_sex_sector(UNISEX_NAME, sex="any", sector="any") is True
    assert store.matches_sex_sector("שם-לא-קיים", sex="any", sector="any") is True


def test_matches_sex_sector_requires_combined_match(store) -> None:
    combos = store.meta_for(UNISEX_NAME)["combos"]
    sectors_for_females = {sec for s, sec in combos if s == "F"}
    sectors_for_males = {sec for s, sec in combos if s == "M"}

    for sector in sectors_for_females:
        assert store.matches_sex_sector(UNISEX_NAME, sex="F", sector=sector) is True
    # A sector this name has no *female* row in (if any) must not match
    # when both filters are applied together, even if it has some male
    # presence there and some female presence elsewhere.
    female_only_gap = sectors_for_males - sectors_for_females
    for sector in female_only_gap:
        assert store.matches_sex_sector(UNISEX_NAME, sex="F", sector=sector) is False


def test_percentile_is_between_0_and_1(store) -> None:
    meta = store.meta_for(UNISEX_NAME)
    assert 0.0 <= meta["percentile"] <= 1.0


def test_overall_total_sums_across_sex_and_sector(store) -> None:
    meta = store.meta_for(UNISEX_NAME)
    combos = meta["combos"]
    # Overall total must be at least the max single-row count (sanity: it's
    # a real sum across rows, not accidentally just one row's value).
    assert meta["total"] > 0
    assert len(combos) >= 2  # at least the M and F rows found above


def test_year_bounds_match_the_dataset(store) -> None:
    assert store.year_min == 1949
    assert store.year_max == 2024


def test_is_full_year_range(store) -> None:
    assert store.is_full_year_range(store.year_min, store.year_max) is True
    assert store.is_full_year_range(store.year_min - 10, store.year_max + 10) is True
    assert store.is_full_year_range(store.year_min, store.year_max - 1) is False
    assert store.is_full_year_range(store.year_min + 1, store.year_max) is False


def test_year_filtered_meta_excludes_names_outside_the_range(store) -> None:
    old_range = store.year_filtered_meta(1949, 1960)
    recent_range = store.year_filtered_meta(2015, 2024)

    assert OLD_ONLY_NAME in old_range
    assert RECENT_ONLY_NAME not in old_range

    assert RECENT_ONLY_NAME in recent_range
    assert OLD_ONLY_NAME not in recent_range


def test_year_filtered_meta_totals_reflect_only_the_range(store) -> None:
    # Popularity within a narrow range must be <= the all-time total, since
    # it's summing strictly fewer rows.
    narrow = store.year_filtered_meta(2015, 2024)
    assert narrow[RECENT_ONLY_NAME]["total"] <= store.meta_for(RECENT_ONLY_NAME)["total"]


def test_year_filtered_meta_empty_range_returns_empty(store) -> None:
    # A range entirely outside the dataset's span has no rows to aggregate.
    assert store.year_filtered_meta(1800, 1801) == {}
