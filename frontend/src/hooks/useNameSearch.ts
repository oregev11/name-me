import { useCallback, useState } from "react";
import { ApiError, searchNames } from "../api/client";
import type { SearchResponse } from "../types/api";

export function useNameSearch() {
  const [likedNames, setLikedNames] = useState<string[]>([]);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runSearch = useCallback(async (names: string[]) => {
    if (names.length === 0) {
      setResult(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await searchNames(names);
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
  }, []);

  const addName = useCallback(
    (name: string) => {
      setLikedNames((prev) => {
        if (prev.includes(name) || prev.length >= 10) return prev;
        const next = [...prev, name];
        void runSearch(next);
        return next;
      });
    },
    [runSearch],
  );

  const removeName = useCallback(
    (name: string) => {
      setLikedNames((prev) => {
        const next = prev.filter((n) => n !== name);
        void runSearch(next);
        return next;
      });
    },
    [runSearch],
  );

  return { likedNames, result, loading, error, addName, removeName };
}
