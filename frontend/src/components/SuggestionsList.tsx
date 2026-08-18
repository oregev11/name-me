import type { SuggestedName } from "../types/api";

interface Props {
  suggestions: SuggestedName[];
  onAdd: (name: string) => void;
}

export function SuggestionsList({ suggestions, onAdd }: Props) {
  if (suggestions.length === 0) return null;

  return (
    <ol className="suggestions-list" dir="rtl">
      {suggestions.map((s) => (
        <li key={s.name}>
          <span className="suggestion-name">{s.name}</span>
          <span className="suggestion-score">
            {(s.similarity * 100).toFixed(0)}%
          </span>
          <button type="button" onClick={() => onAdd(s.name)}>
            הוסף
          </button>
        </li>
      ))}
    </ol>
  );
}
