import { render, screen } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { YearRangeSlider } from "../src/components/YearRangeSlider";

describe("YearRangeSlider", () => {
  it("shows 'כל השנים' when the value spans the full range", () => {
    render(
      <YearRangeSlider
        min={1949}
        max={2024}
        value={[1949, 2024]}
        onChange={vi.fn()}
        disabled={false}
      />,
    );
    expect(screen.getByText("כל השנים")).toBeInTheDocument();
  });

  it("shows the numeric range when narrowed", () => {
    render(
      <YearRangeSlider
        min={1949}
        max={2024}
        value={[1990, 2010]}
        onChange={vi.fn()}
        disabled={false}
      />,
    );
    expect(screen.getByText("1990–2010")).toBeInTheDocument();
  });

  it("calls onChange with the new lower bound clamped to not exceed the upper bound", () => {
    const onChange = vi.fn();
    render(
      <YearRangeSlider
        min={1949}
        max={2024}
        value={[1990, 2000]}
        onChange={onChange}
        disabled={false}
      />,
    );
    fireEvent.change(screen.getByLabelText("משנת"), {
      target: { value: "2010" },
    });
    expect(onChange).toHaveBeenCalledWith([2000, 2000]);
  });

  it("calls onChange with the new upper bound clamped to not go below the lower bound", () => {
    const onChange = vi.fn();
    render(
      <YearRangeSlider
        min={1949}
        max={2024}
        value={[1990, 2000]}
        onChange={onChange}
        disabled={false}
      />,
    );
    fireEvent.change(screen.getByLabelText("עד שנת"), {
      target: { value: "1980" },
    });
    expect(onChange).toHaveBeenCalledWith([1990, 1990]);
  });

  it("disables both handles when disabled is true", () => {
    render(
      <YearRangeSlider
        min={1949}
        max={2024}
        value={[1949, 2024]}
        onChange={vi.fn()}
        disabled={true}
      />,
    );
    expect(screen.getByLabelText("משנת")).toBeDisabled();
    expect(screen.getByLabelText("עד שנת")).toBeDisabled();
  });
});
