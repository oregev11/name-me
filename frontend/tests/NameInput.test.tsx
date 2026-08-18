import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NameInput } from "../src/components/NameInput";

vi.mock("../src/api/client", () => ({
  autocompleteNames: vi.fn().mockResolvedValue({ matches: ["דוד", "דודי"] }),
}));

describe("NameInput", () => {
  it("adds a chip when Enter is pressed with a valid Hebrew name", () => {
    const onAdd = vi.fn();
    render(<NameInput onAdd={onAdd} disabled={false} />);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "דוד" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onAdd).toHaveBeenCalledWith("דוד");
  });

  it("does not add on Enter for non-Hebrew input", () => {
    const onAdd = vi.fn();
    render(<NameInput onAdd={onAdd} disabled={false} />);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "David" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onAdd).not.toHaveBeenCalled();
  });

  it("adds a chip when an autocomplete suggestion is clicked", async () => {
    const onAdd = vi.fn();
    render(<NameInput onAdd={onAdd} disabled={false} />);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "דו" } });

    const suggestion = await waitFor(() => screen.getByText("דודי"));
    fireEvent.click(suggestion);

    expect(onAdd).toHaveBeenCalledWith("דודי");
  });
});
