import { useEffect, useRef, useState } from "react";
import { autocompleteNames } from "../api/client";

interface Props {
  onAdd: (name: string) => void;
  disabled: boolean;
}

const HEBREW_NAME_RE = /^[א-ת][א-ת \-'"]*$/;

export function NameInput({ onAdd, disabled }: Props) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );

  useEffect(() => {
    clearTimeout(debounceRef.current);
    const trimmed = query.trim();
    if (!trimmed) {
      setSuggestions([]);
      return;
    }
    debounceRef.current = setTimeout(() => {
      autocompleteNames(trimmed)
        .then((res) => setSuggestions(res.matches))
        .catch(() => setSuggestions([]));
    }, 200);
    return () => clearTimeout(debounceRef.current);
  }, [query]);

  function commit(name: string) {
    const trimmed = name.trim();
    if (!trimmed || !HEBREW_NAME_RE.test(trimmed)) return;
    onAdd(trimmed);
    setQuery("");
    setSuggestions([]);
  }

  return (
    <div className="name-input">
      <input
        dir="rtl"
        type="text"
        value={query}
        disabled={disabled}
        placeholder="הקלידו שם עברי, למשל: נועה"
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit(query);
        }}
        aria-label="הוספת שם אהוב"
      />
      {suggestions.length > 0 && (
        <ul className="autocomplete-list" dir="rtl">
          {suggestions.map((name) => (
            <li key={name}>
              <button type="button" onClick={() => commit(name)}>
                {name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
