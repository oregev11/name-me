import { useCallback, useState } from "react";
import { ApiError, searchNames } from "../api/client";
import type { ModelId, SearchResponse } from "../types/api";

export function useNameSearch() {
  const [likedNames, setLikedNames] = useState<string[]>([]);
  const [model, setModelState] = useState<ModelId>("written_similarity");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runSearch = useCallback(
    async (names: string[], searchModel: ModelId) => {
      if (names.length === 0) {
        setResult(null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const response = await searchNames(names, searchModel);
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
        void runSearch(next, model);
        return next;
      });
    },
    [runSearch, model],
  );

  const removeName = useCallback(
    (name: string) => {
      setLikedNames((prev) => {
        const next = prev.filter((n) => n !== name);
        void runSearch(next, model);
        return next;
      });
    },
    [runSearch, model],
  );

  const setModel = useCallback(
    (nextModel: ModelId) => {
      setModelState(nextModel);
      // Re-run the current liked names against the newly selected model --
      // switching models jumps to a different (unrelated) 2D PCA space, so
      // this is a deliberate re-search, not a smooth "refine" step.
      void runSearch(likedNames, nextModel);
    },
    [likedNames, runSearch],
  );

  return {
    likedNames,
    model,
    result,
    loading,
    error,
    addName,
    removeName,
    setModel,
  };
}
