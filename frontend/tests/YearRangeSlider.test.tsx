import { render, screen } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { YearRangeSlider } from "../src/components/YearRangeSlider";

describe("YearRangeSlider", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

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

  it("updates the displayed value immediately, without waiting for the debounce", () => {
    render(
      <YearRangeSlider
        min={1949}
        max={2024}
        value={[1990, 2000]}
        onChange={vi.fn()}
        disabled={false}
      />,
    );
    fireEvent.change(screen.getByLabelText("משנת"), {
      target: { value: "1995" },
    });
    // The label reflects the drag instantly -- this is what keeps a drag
    // feeling fluid even though the network-triggering onChange is debounced.
    expect(screen.getByText("1995–2000")).toBeInTheDocument();
  });

  it("debounces onChange with the new lower bound clamped to not exceed the upper bound", () => {
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
    expect(onChange).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(onChange).toHaveBeenCalledWith([2000, 2000]);
  });

  it("debounces onChange with the new upper bound clamped to not go below the lower bound", () => {
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
    vi.runAllTimers();
    expect(onChange).toHaveBeenCalledWith([1990, 1990]);
  });

  it("collapses a rapid sequence of drag steps into a single committed onChange call", () => {
    // Regression test for TASKS..md #8: every intermediate step (as a real
    // mouse drag produces many of) must NOT each call onChange -- only the
    // final settled value, once, after the drag pauses.
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
    const handle = screen.getByLabelText("משנת");
    for (const year of [1991, 1992, 1993, 1994, 1995]) {
      fireEvent.change(handle, { target: { value: String(year) } });
    }
    expect(onChange).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith([1995, 2000]);
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
