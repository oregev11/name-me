import type {
  PopularityFilter,
  SearchFilters as SearchFiltersType,
  SexFilter,
} from "../types/api";

interface Props {
  value: SearchFiltersType;
  onChange: (patch: Partial<SearchFiltersType>) => void;
  disabled: boolean;
}

const SEX_OPTIONS: { value: SexFilter; label: string }[] = [
  { value: "any", label: "כל המינים" },
  { value: "M", label: "בנים" },
  { value: "F", label: "בנות" },
];

const POPULARITY_OPTIONS: { value: PopularityFilter; label: string }[] = [
  { value: "all", label: "כל השמות" },
  { value: "top_10_percent", label: "הנפוצים ביותר (10%)" },
  { value: "top_90_percent", label: "רוב השמות (90%)" },
];

const SORT_OPTIONS: { value: SearchFiltersType["sort"]; label: string }[] = [
  { value: "similar", label: "הכי דומים" },
  { value: "dissimilar", label: "הכי שונים" },
];

export function SearchFilters({ value, onChange, disabled }: Props) {
  return (
    <div className="search-filters" dir="rtl">
      <label className="search-filter">
        <span>מין</span>
        <select
          value={value.sex}
          disabled={disabled}
          onChange={(e) => onChange({ sex: e.target.value as SexFilter })}
        >
          {SEX_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>

      <label className="search-filter">
        <span>נפוצות</span>
        <select
          value={value.popularity}
          disabled={disabled}
          onChange={(e) =>
            onChange({ popularity: e.target.value as PopularityFilter })
          }
        >
          {POPULARITY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>

      <div className="search-filter">
        <span>סדר</span>
        <div
          className="search-filter-buttons"
          role="radiogroup"
          aria-label="סדר תוצאות"
        >
          {SORT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              role="radio"
              aria-checked={value.sort === opt.value}
              className={`search-filter-btn${value.sort === opt.value ? " active" : ""}`}
              disabled={disabled}
              onClick={() => onChange({ sort: opt.value })}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
