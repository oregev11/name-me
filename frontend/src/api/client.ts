import type {
  AutocompleteResponse,
  HealthResponse,
  ModelId,
  SearchFilters,
  SearchResponse,
} from "../types/api";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

// Structured error body the backend sends for known, specific failure
// cases -- see backend/src/nameme/api/routes_search.py's
// UnsupportedOovNameError handling. `error` is a stable machine-matchable
// tag; `message` is a human (English/dev-facing, matching backend
// convention) explanation, not meant to be shown to end users verbatim --
// see useNameSearch.ts for the Hebrew translation per `error` tag.
interface ApiErrorDetail {
  error: string;
  message: string;
  [key: string]: unknown;
}

export class ApiError extends Error {
  /** Present only when the backend returned a structured `detail` object
   * (not just a plain string) -- absent for network failures, 5xx errors,
   * or FastAPI's default Pydantic-validation error shape. */
  detail?: ApiErrorDetail;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const bodyText = await res.text();
    const err = new ApiError(`${res.status} ${res.statusText}: ${bodyText}`);
    try {
      const parsed: unknown = JSON.parse(bodyText);
      const detail = (parsed as { detail?: unknown })?.detail;
      if (detail && typeof detail === "object" && "error" in detail) {
        err.detail = detail as ApiErrorDetail;
      }
    } catch {
      // Not JSON (e.g. a proxy's plain-text error page) -- err.detail
      // stays unset, callers fall back to the generic message.
    }
    throw err;
  }
  return res.json() as Promise<T>;
}

export function searchNames(
  likedNames: string[],
  model: ModelId,
  filters: SearchFilters,
  topK = 20,
): Promise<SearchResponse> {
  return request<SearchResponse>("/api/search", {
    method: "POST",
    body: JSON.stringify({
      liked_names: likedNames,
      top_k: topK,
      model,
      sex: filters.sex,
      sector: filters.sector,
      popularity: filters.popularity,
      sort: filters.sort,
      year_min: filters.yearMin,
      year_max: filters.yearMax,
    }),
  });
}

export function autocompleteNames(
  query: string,
  limit = 8,
): Promise<AutocompleteResponse> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  return request<AutocompleteResponse>(
    `/api/autocomplete?${params.toString()}`,
  );
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}
