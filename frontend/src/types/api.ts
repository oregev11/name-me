// Mirrors backend/src/nameme/schemas/search.py

export type ModelId = "written_similarity" | "cultural_similarity";
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
}
