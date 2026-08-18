import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScatterChart } from "../src/components/ScatterChart";
import type { NamePoint, SuggestedName } from "../src/types/api";

const liked: NamePoint[] = [{ name: "דוד", x: 0.1, y: 0.2 }];
const suggestions: SuggestedName[] = [
  {
    name: "דודי",
    x: 0.15,
    y: 0.22,
    similarity: 0.9,
    sex: "M",
    popularity: 100,
  },
  { name: "דן", x: 0.05, y: 0.1, similarity: 0.6, sex: "M", popularity: 50 },
];

beforeEach(() => {
  // Recharts' ResponsiveContainer needs a non-zero size to render its
  // children; jsdom reports 0x0 by default.
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(600);
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(360);
});

describe("ScatterChart", () => {
  it("renders a point for each liked name and each suggestion", () => {
    const { container } = render(
      <ScatterChart liked={liked} suggestions={suggestions} />,
    );

    const symbols = container.querySelectorAll(".recharts-scatter-symbol");
    expect(symbols.length).toBe(liked.length + suggestions.length);
  });
});
