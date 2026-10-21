export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  database: string;
}

export interface Node {
  id: string;
  type: string;
  name: string;
  file_path: string;
  line_start: number;
  line_end: number;
  metadata: Record<string, unknown>;
}

export interface Edge {
  id: string;
  source: string;
  target: string;
  type: string;
  metadata: Record<string, unknown>;
}

export interface GraphResponse {
  nodes: Node[];
  edges: Edge[];
  total_nodes: number;
  total_edges: number;
}

export interface GraphQuery {
  node_type?: string;
  edge_type?: string;
  file_path?: string;
  limit?: number;
  offset?: number;
}

const API_BASE = "/api/v1";

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

export const api = {
  health: () => fetchJson<HealthResponse>("/health"),
  graph: {
    list: (query?: GraphQuery) => {
      const params = new URLSearchParams();
      if (query) {
        Object.entries(query).forEach(([key, value]) => {
          if (value !== undefined) params.append(key, String(value));
        });
      }
      return fetchJson<GraphResponse>(`${API_BASE}/graph?${params.toString()}`);
    },
    parse: (path: string) =>
      fetchJson<{ status: string; path: string; parsed_files: number; nodes: number; edges: number }>(
        `${API_BASE}/graph/parse`,
        {
          method: "POST",
          body: JSON.stringify({ path }),
        }
      ),
    export: (format: string = "json") =>
      fetchJson<{ format: string; data: string }>(`${API_BASE}/graph/export?format=${format}`),
  },
};