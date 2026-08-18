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
            suggestion actually is, not just how similar it is. */}
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
        <Scatter
          name="שמות אהובים"
          data={liked}
          fill="var(--liked)"
          shape="star"
        />
      </RechartsScatterChart>
    </ResponsiveContainer>
  );
}
