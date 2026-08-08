// OBSTACK Phase E.5 — TS mirror of eaasp_common.MemoriesClient
// models. 1:1 mirror of tools/eaasp-common/.../memories_models.py.
// When grid-server changes a wire field, both these files (and
// the Python parent) get updated together.

export interface ListMemoriesParams {
  limit: number;
  session_id?: string | null;
  q?: string | null;
}

export interface ListMemoriesResponse {
  results: Record<string, unknown>[];
}

export interface WorkingMemoryBlock {
  id: string;
  kind?: string;
  label?: string;
  value?: string;
  priority?: number;
  char_limit?: number;
  is_readonly?: boolean;
}

export interface WorkingMemoryResponse {
  blocks: WorkingMemoryBlock[];
}

export interface MemoriesClientOptions {
  baseUrl: string;
  authToken?: string | null;
  getToken?: () => string | null;
}
