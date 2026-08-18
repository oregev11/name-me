import {
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart as RechartsScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import type { NamePoint, SuggestedName } from "../types/api";

interface Props {
  liked: NamePoint[];
  suggestions: SuggestedName[];
}

interface TooltipPayloadEntry {
  payload: NamePoint | SuggestedName;
}

const SEX_LABEL: Record<string, string> = { M: "בן", F: "בת" };
const SEX_COLOR: Record<string, string> = {
  M: "#3b82f6",
  F: "#db2777",
};

function isSuggestion(
  point: NamePoint | SuggestedName,
): point is SuggestedName {
  return "similarity" in point;
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="scatter-tooltip" dir="rtl">
      <strong>{point.name}</strong>
      {isSuggestion(point) && (
        <>
          <div>דמיון: {(point.similarity * 100).toFixed(0)}%</div>
          <div>
            {SEX_LABEL[point.sex] ?? point.sex} · פופולריות:{" "}
            {point.popularity.toLocaleString("he")}
          </div>
        </>
      )}
    </div>
  );
}

/** Points of a 5-pointed star centered at (cx, cy). */
function starPoints(
  cx: number,
  cy: number,
  outerR: number,
  innerR: number,
): string {
  const pts: string[] = [];
  for (let i = 0; i < 10; i++) {
    const r = i % 2 === 0 ? outerR : innerR;
    const angle = (Math.PI / 5) * i - Math.PI / 2;
    pts.push(`${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`);
  }
  return pts.join(" ");
}

/**
 * Custom shape for liked ("selected") names -- deliberately NOT tied to the
 * popularity-driven ZAxis size used for suggestions, so a liked name always
 * renders large and identical in size regardless of its own popularity.
 * Renders on top of suggestion bubbles (last in the JSX = top of SVG
 * z-order) with a white outline for contrast, plus the name printed right
 * above it so it's identifiable without hovering -- the whole point being
 * that liked/selected names should never be mistaken for a suggestion.
 */
function LikedPointShape(props: {
  cx?: number;
  cy?: number;
  payload?: NamePoint;
}) {
  const { cx = 0, cy = 0, payload } = props;
  return (
    <g>
      <polygon
        points={starPoints(cx, cy, 13, 5.5)}
        fill="var(--liked)"
        stroke="white"
        strokeWidth={1.5}
      />
      {payload && (
        <text
          x={cx}
          y={cy - 18}
          textAnchor="middle"
          fontSize={12}
          fontWeight={700}
          fill="var(--liked)"
          stroke="var(--surface)"
          strokeWidth={3}
          paintOrder="stroke"
        >
          {payload.name}
        </text>
      )}
    </g>
  );
}

export function ScatterChart({ liked, suggestions }: Props) {
  const suggestionsM = suggestions.filter((s) => s.sex === "M");
  const suggestionsF = suggestions.filter((s) => s.sex === "F");

  return (
    <ResponsiveContainer width="100%" height={380}>
      <RechartsScatterChart
        margin={{ top: 10, right: 20, bottom: 10, left: 20 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis type="number" dataKey="x" hide />
        <YAxis type="number" dataKey="y" hide />
        {/* Point size reflects real-world popularity -- a bubble-chart size
            channel, so a glance at the map hints at how common each
            suggestion actually is, not just how similar it is. Liked
            points use a fixed size instead (see LikedPointShape), so they
            never shrink to match this scale. */}
        <ZAxis type="number" dataKey="popularity" range={[40, 260]} />
        <Tooltip content={<ChartTooltip />} />
        <Legend
          verticalAlign="top"
          height={32}
          formatter={(value: string) => (
            <span style={{ color: "var(--text)" }}>{value}</span>
          )}
        />
        <Scatter
          name="הצעות - בנים"
          data={suggestionsM}
          fill={SEX_COLOR.M}
          fillOpacity={0.75}
        />
        <Scatter
          name="הצעות - בנות"
          data={suggestionsF}
          fill={SEX_COLOR.F}
          fillOpacity={0.75}
        />
        <Scatter name="שמות אהובים" data={liked} shape={LikedPointShape} />
      </RechartsScatterChart>
    </ResponsiveContainer>
  );
}
