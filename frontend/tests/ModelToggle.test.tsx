import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ModelToggle } from "../src/components/ModelToggle";

describe("ModelToggle", () => {
  it("renders both options with correct Hebrew labels", () => {
    render(
      <ModelToggle
        value="written_similarity"
        onChange={vi.fn()}
        disabled={false}
      />,
    );
    expect(screen.getByText("דמיון כתיב")).toBeInTheDocument();
    expect(screen.getByText("דמיון תרבותי ומשמעות")).toBeInTheDocument();
  });

  it("marks the selected option as checked via aria-checked", () => {
    render(
      <ModelToggle
        value="cultural_similarity"
        onChange={vi.fn()}
        disabled={false}
      />,
    );
    expect(screen.getByText("דמיון כתיב")).toHaveAttribute(
      "aria-checked",
      "false",
    );
    expect(screen.getByText("דמיון תרבותי ומשמעות")).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("calls onChange with the clicked option's id", () => {
    const onChange = vi.fn();
    render(
      <ModelToggle
        value="written_similarity"
        onChange={onChange}
        disabled={false}
      />,
    );
    fireEvent.click(screen.getByText("דמיון תרבותי ומשמעות"));
    expect(onChange).toHaveBeenCalledWith("cultural_similarity");
  });

  it("shows a Hebrew explanation of the currently selected model, switching with the value", () => {
    const { rerender } = render(
      <ModelToggle
        value="written_similarity"
        onChange={vi.fn()}
        disabled={false}
      />,
    );
    expect(screen.getByText(/איך שהם כתובים/)).toBeInTheDocument();

    rerender(
      <ModelToggle
        value="cultural_similarity"
        onChange={vi.fn()}
        disabled={false}
      />,
    );
    expect(screen.getByText(/שיטה ניסיונית/)).toBeInTheDocument();
    expect(screen.queryByText(/איך שהם כתובים/)).not.toBeInTheDocument();
  });

  it("disables both buttons when disabled is true", () => {
    render(
      <ModelToggle
        value="written_similarity"
        onChange={vi.fn()}
        disabled={true}
      />,
    );
    expect(screen.getByText("דמיון כתיב")).toBeDisabled();
    expect(screen.getByText("דמיון תרבותי ומשמעות")).toBeDisabled();
  });
});
