// Mirrors backend/src/nameme/schemas/search.py

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

export interface HealthResponse {
  status: string;
  corpus_size: number;
  embedder_type: string;
}
