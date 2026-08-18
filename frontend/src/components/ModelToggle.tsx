import type { ModelId } from "../types/api";

interface Props {
  value: ModelId;
  onChange: (model: ModelId) => void;
  disabled: boolean;
}

const OPTIONS: { id: ModelId; label: string }[] = [
  { id: "written_similarity", label: "דמיון כתיב" },
  { id: "cultural_similarity", label: "דמיון תרבותי ומשמעות" },
];

export function ModelToggle({ value, onChange, disabled }: Props) {
  return (
    <div className="model-toggle" dir="rtl">
      <div
        role="radiogroup"
        aria-label="שיטת דמיון"
        className="model-toggle-buttons"
      >
        {OPTIONS.map((opt) => (
          <button
            key={opt.id}
            type="button"
            role="radio"
            aria-checked={value === opt.id}
            className={`model-toggle-btn${value === opt.id ? " active" : ""}`}
            disabled={disabled}
            onClick={() => onChange(opt.id)}
          >
            {opt.label}
          </button>
        ))}
      </div>
      <p className="model-toggle-hint">מעבר בין שיטות בונה מפה חדשה מאפס</p>
    </div>
  );
}
