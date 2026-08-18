import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart as RechartsScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { NamePoint, SuggestedName } from "../types/api";

interface Props {
  liked: NamePoint[];
  suggestions: SuggestedName[];
}

interface TooltipPayloadEntry {
  payload: NamePoint | SuggestedName;
}

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
        <div>דמיון: {(point.similarity * 100).toFixed(0)}%</div>
      )}
    </div>
  );
}

export function ScatterChart({ liked, suggestions }: Props) {
  return (
    <ResponsiveContainer width="100%" height={360}>
      <RechartsScatterChart
        margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis type="number" dataKey="x" hide />
        <YAxis type="number" dataKey="y" hide />
        <Tooltip content={<ChartTooltip />} />
        <Scatter
          name="הצעות"
          data={suggestions}
          fill="var(--accent)"
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
