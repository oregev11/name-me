import type { AutocompleteResponse, SearchResponse } from "../types/api";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export function searchNames(
  likedNames: string[],
  topK = 10,
): Promise<SearchResponse> {
  return request<SearchResponse>("/api/search", {
    method: "POST",
    body: JSON.stringify({ liked_names: likedNames, top_k: topK }),
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
