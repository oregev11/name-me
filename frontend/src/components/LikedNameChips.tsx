interface Props {
  names: string[];
  onRemove: (name: string) => void;
}

export function LikedNameChips({ names, onRemove }: Props) {
  if (names.length === 0) {
    return <p className="empty-hint">הוסיפו שם או שניים כדי להתחיל</p>;
  }

  return (
    <ul className="chip-list" dir="rtl">
      {names.map((name) => (
        <li key={name} className="chip">
          <span>{name}</span>
          <button
            type="button"
            aria-label={`הסר את ${name}`}
            onClick={() => onRemove(name)}
          >
            ×
          </button>
        </li>
      ))}
    </ul>
  );
}
