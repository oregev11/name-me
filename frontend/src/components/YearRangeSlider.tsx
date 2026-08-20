import { useEffect, useRef, useState } from "react";

interface Props {
  min: number;
  max: number;
  value: [number, number]; // [from, to] -- always within [min, max]
  onChange: (value: [number, number]) => void;
  disabled: boolean;
}

// How long to wait, after the user stops moving a handle, before actually
// calling `onChange` (which triggers a search and flips `disabled` while
// it's in flight). Without this, EVERY single one-year step fired its own
// search -- and disabling the input mid-drag drops the browser's mouse
// capture, ending the drag right there. That's what made the slider only
// ever move "one year at a time" (see TASKS..md #8): each step killed its
// own gesture. Debouncing means a whole drag across decades stays one
// fluid, uninterrupted gesture, with a single search firing once it settles.
const COMMIT_DELAY_MS = 300;

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
  // Local copy, updated instantly on every drag step so the handles/fill/
  // label always track the pointer -- `onChange` itself is debounced (see
  // above), so it can't be what drives the visible position.
  const [local, setLocal] = useState(value);
  const commitTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );

  // Resync if the *bounds* change from outside (e.g. filters reset
  // elsewhere) -- keyed on the values, not the array reference, so a
  // parent re-render mid-drag (new array, same numbers) can't stomp on an
  // uncommitted local drag.
  useEffect(() => {
    setLocal(value);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value[0], value[1]]);

  useEffect(() => () => clearTimeout(commitTimer.current), []);

  const commit = (next: [number, number]) => {
    setLocal(next);
    clearTimeout(commitTimer.current);
    commitTimer.current = setTimeout(() => onChange(next), COMMIT_DELAY_MS);
  };

  const [from, to] = local;
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
          onChange={(e) => commit([Math.min(Number(e.target.value), to), to])}
        />
        <input
          type="range"
          aria-label="עד שנת"
          min={min}
          max={max}
          value={to}
          disabled={disabled}
          onChange={(e) =>
            commit([from, Math.max(Number(e.target.value), from)])
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
