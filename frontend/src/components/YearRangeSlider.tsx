interface Props {
  min: number;
  max: number;
  value: [number, number]; // [from, to] -- always within [min, max]
  onChange: (value: [number, number]) => void;
  disabled: boolean;
}

/**
 * A dual-handle "ruler" for picking a year range. Built from two native
 * `<input type="range">` elements stacked on top of each other (a common,
 * dependency-free technique) rather than a custom drag implementation, so
 * keyboard/touch/accessibility all come from the browser for free.
 */
export function YearRangeSlider({
  min,
  max,
  value,
  onChange,
  disabled,
}: Props) {
  const [from, to] = value;
  const span = Math.max(max - min, 1);
  const pctFrom = ((from - min) / span) * 100;
  const pctTo = ((to - min) / span) * 100;
  const isFullRange = from === min && to === max;

  return (
    <div className="year-range" dir="ltr">
      <div className="year-range-header" dir="rtl">
        <span>שנות לידה</span>
        <span className="year-range-values">
          {isFullRange ? "כל השנים" : `${from}–${to}`}
        </span>
      </div>
      <div className="year-range-track">
        <div className="year-range-rail" />
        <div
          className="year-range-fill"
          style={{ left: `${pctFrom}%`, right: `${100 - pctTo}%` }}
        />
        <input
          type="range"
          aria-label="משנת"
          min={min}
          max={max}
          value={from}
          disabled={disabled}
          onChange={(e) => onChange([Math.min(Number(e.target.value), to), to])}
        />
        <input
          type="range"
          aria-label="עד שנת"
          min={min}
          max={max}
          value={to}
          disabled={disabled}
          onChange={(e) =>
            onChange([from, Math.max(Number(e.target.value), from)])
          }
        />
      </div>
      <div className="year-range-bounds">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}
