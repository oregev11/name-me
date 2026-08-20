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

// Plain-language explanation of what each model actually does, shown below
// the toggle so a non-technical user understands the difference before
// picking one -- not just the (fairly opaque, on its own) button labels.
// See root README's "The two similarity models" section for the full
// technical version this simplifies.
const MODEL_EXPLANATIONS: Record<ModelId, string> = {
  written_similarity:
    'משווה בין שמות לפי איך שהם כתובים (אותיות משותפות) -- למשל "דוד" ו"דודי" יתקבלו כדומים כי הם חולקים אותיות. שיטה יציבה ומדויקת, אך לא "מבינה" קשר תרבותי או משמעות מאחורי השם.',
  cultural_similarity:
    'שיטה ניסיונית המבוססת על בינה מלאכותית, שמנסה לאתר קשר תרבותי או משמעותי בין שמות גם כשהם כתובים אחרת לגמרי (למשל שמות מקראיים קרובים). התוצאות מעניינות אך פחות מוכחות משיטת "דמיון כתיב".',
};

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
      <p className="model-toggle-explanation">{MODEL_EXPLANATIONS[value]}</p>
      <p className="model-toggle-hint">מעבר בין שיטות בונה מפה חדשה מאפס</p>
    </div>
  );
}
