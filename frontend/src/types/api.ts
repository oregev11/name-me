// Mirrors backend/src/nameme/schemas/search.py

export type ModelId = "written_similarity" | "cultural_similarity";

export interface NamePoint {
  name: string;
  x: number;
  y: number;
}

export interface SuggestedName extends NamePoint {
  similarity: number;
  sex: "M" | "F";
  popularity: number;
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
