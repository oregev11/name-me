import { useCallback, useState } from "react";
import { ApiError, searchNames } from "../api/client";
import type { ModelId, SearchFilters, SearchResponse } from "../types/api";

const DEFAULT_FILTERS: SearchFilters = {
  sex: "any",
  sector: "any",
  popularity: "all",
  sort: "similar",
};

export function useNameSearch() {
  const [likedNames, setLikedNames] = useState<string[]>([]);
  const [model, setModelState] = useState<ModelId>("written_similarity");
  const [filters, setFiltersState] = useState<SearchFilters>(DEFAULT_FILTERS);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runSearch = useCallback(
    async (
      names: string[],
      searchModel: ModelId,
      searchFilters: SearchFilters,
    ) => {
      if (names.length === 0) {
        setResult(null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const response = await searchNames(names, searchModel, searchFilters);
        setResult(response);
      } catch (err) {
        const message =
          err instanceof ApiError
            ? "לא הצלחנו להביא תוצאות. אולי שרת המודל בהתעוררות (יכול לקחת עד דקה)."
            : "שגיאה לא צפויה, נסו שוב.";
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  const addName = useCallback(
    (name: string) => {
      setLikedNames((prev) => {
        if (prev.includes(name) || prev.length >= 10) return prev;
        const next = [...prev, name];
        void runSearch(next, model, filters);
        return next;
      });
    },
    [runSearch, model, filters],
  );

  const removeName = useCallback(
    (name: string) => {
      setLikedNames((prev) => {
        const next = prev.filter((n) => n !== name);
        void runSearch(next, model, filters);
        return next;
      });
    },
    [runSearch, model, filters],
  );

  const setModel = useCallback(
    (nextModel: ModelId) => {
      setModelState(nextModel);
      // Re-run the current liked names against the newly selected model --
      // switching models jumps to a different (unrelated) 2D PCA space, so
      // this is a deliberate re-search, not a smooth "refine" step.
      void runSearch(likedNames, nextModel, filters);
    },
    [likedNames, filters, runSearch],
  );

  const setFilters = useCallback(
    (patch: Partial<SearchFilters>) => {
      setFiltersState((prev) => {
        const next = { ...prev, ...patch };
        void runSearch(likedNames, model, next);
        return next;
      });
    },
    [likedNames, model, runSearch],
  );

  return {
    likedNames,
    model,
    filters,
    result,
    loading,
    error,
    addName,
    removeName,
    setModel,
    setFilters,
  };
}
