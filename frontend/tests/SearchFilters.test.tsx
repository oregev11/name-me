import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SearchFilters } from "../src/components/SearchFilters";
import type { SearchFilters as SearchFiltersType } from "../src/types/api";

const DEFAULT: SearchFiltersType = {
  sex: "any",
  sector: "any",
  popularity: "all",
  sort: "similar",
};

describe("SearchFilters", () => {
  it("calls onChange with the selected sex", () => {
    const onChange = vi.fn();
    render(
      <SearchFilters value={DEFAULT} onChange={onChange} disabled={false} />,
    );
    fireEvent.change(screen.getByDisplayValue("כל המינים"), {
      target: { value: "F" },
    });
    expect(onChange).toHaveBeenCalledWith({ sex: "F" });
  });

  it("calls onChange with the selected sector", () => {
    const onChange = vi.fn();
    render(
      <SearchFilters value={DEFAULT} onChange={onChange} disabled={false} />,
    );
    fireEvent.change(screen.getByDisplayValue("כל המגזרים"), {
      target: { value: "Muslim" },
    });
    expect(onChange).toHaveBeenCalledWith({ sector: "Muslim" });
  });

  it("calls onChange with the selected popularity filter", () => {
    const onChange = vi.fn();
    render(
      <SearchFilters value={DEFAULT} onChange={onChange} disabled={false} />,
    );
    fireEvent.change(screen.getByDisplayValue("כל השמות"), {
      target: { value: "top_10_percent" },
    });
    expect(onChange).toHaveBeenCalledWith({ popularity: "top_10_percent" });
  });

  it("calls onChange with the selected sort mode", () => {
    const onChange = vi.fn();
    render(
      <SearchFilters value={DEFAULT} onChange={onChange} disabled={false} />,
    );
    fireEvent.click(screen.getByText("הכי שונים"));
    expect(onChange).toHaveBeenCalledWith({ sort: "dissimilar" });
  });

  it("marks the active sort button via aria-checked", () => {
    render(
      <SearchFilters
        value={{ ...DEFAULT, sort: "dissimilar" }}
        onChange={vi.fn()}
        disabled={false}
      />,
    );
    expect(screen.getByText("הכי דומים")).toHaveAttribute(
      "aria-checked",
      "false",
    );
    expect(screen.getByText("הכי שונים")).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("disables all controls when disabled is true", () => {
    render(
      <SearchFilters value={DEFAULT} onChange={vi.fn()} disabled={true} />,
    );
    expect(screen.getByDisplayValue("כל המינים")).toBeDisabled();
    expect(screen.getByDisplayValue("כל המגזרים")).toBeDisabled();
    expect(screen.getByDisplayValue("כל השמות")).toBeDisabled();
    expect(screen.getByText("הכי דומים")).toBeDisabled();
  });
});
