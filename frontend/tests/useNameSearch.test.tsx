import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../src/api/client";
import { useNameSearch } from "../src/hooks/useNameSearch";

vi.mock("../src/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/api/client")>();
  return {
    ...actual,
    getHealth: vi.fn().mockResolvedValue({
      status: "ok",
      corpus_size: 19882,
      models: [],
      year_min: 1949,
      year_max: 2024,
    }),
    searchNames: vi.fn(),
  };
});

// Imported after the mock so this refers to the mocked function.
import { searchNames } from "../src/api/client";

describe("useNameSearch", () => {
  it("shows a specific Hebrew message for an unsupported-OOV-name error, not the generic fallback", async () => {
    const err = new ApiError("422 Unprocessable Entity");
    err.detail = {
      error: "unsupported_oov_name",
      model: "cultural_similarity",
      names: ["קסניופולוס"],
      message: "cultural_similarity does not support names outside its corpus",
    };
    vi.mocked(searchNames).mockRejectedValueOnce(err);

    const { result } = renderHook(() => useNameSearch());

    act(() => {
      result.current.addName("קסניופולוס");
    });

    await waitFor(() => expect(result.current.error).not.toBeNull());

    expect(result.current.error).toContain("קסניופולוס");
    expect(result.current.error).toContain("דמיון תרבותי ומשמעות");
    // Must NOT fall back to the generic "server might be waking up" message.
    expect(result.current.error).not.toContain("בהתעוררות");
  });

  it("falls back to the generic message for an unstructured ApiError", async () => {
    vi.mocked(searchNames).mockRejectedValueOnce(
      new ApiError("500 Internal Server Error"),
    );

    const { result } = renderHook(() => useNameSearch());

    act(() => {
      result.current.addName("דוד");
    });

    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.error).toContain("בהתעוררות");
  });
});
