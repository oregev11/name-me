// Mirrors backend/src/nameme/schemas/search.py

export type ModelId = "written_similarity" | "cultural_similarity";

// Single source of truth for each model's Hebrew display name -- shared by
// ModelToggle (the toggle buttons) and useNameSearch (error messages that
// need to name a model in user-facing text), so both stay in sync instead
// of duplicating/drifting from each other. Lives here rather than in
// ModelToggle.tsx so that component file only exports the component
// itself (React Fast Refresh works reliably only when a file's exports are
// either all components or all non-components).
export const MODEL_LABELS: Record<ModelId, string> = {
  written_similarity: "דמיון כתיב",
  cultural_similarity: "דמיון תרבותי ומשמעות",
};
export type SexFilter = "any" | "M" | "F";
export type SectorFilter =
  "any" | "Jewish" | "Muslim" | "Christian-Arab" | "Druze";
export type PopularityFilter = "all" | "top_10_percent" | "top_90_percent";
export type SortMode = "similar" | "dissimilar";

export interface SearchFilters {
  sex: SexFilter;
  sector: SectorFilter;
  popularity: PopularityFilter;
  sort: SortMode;
  // Both null means "no year filter" (the full dataset range).
  yearMin: number | null;
  yearMax: number | null;
}

export interface NamePoint {
  name: string;
  x: number;
  y: number;
}

export interface SuggestedName extends NamePoint {
  similarity: number;
  sex: "M" | "F";
  popularity: number;
  sectors: string[];
}

export interface SearchResponse {
  liked: NamePoint[];
  suggestions: SuggestedName[];
}

export interface AutocompleteResponse {
  matches: string[];
}

export interface ModelInfo {
  id: string;
  display_name: string;
  dim: number;
  corpus_vectors: number;
}

export interface HealthResponse {
  status: string;
  corpus_size: number;
  models: ModelInfo[];
  year_min: number;
  year_max: number;
}
