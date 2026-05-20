const BASE = "http://localhost:8765";

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${method} ${path} → ${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const get = <T>(path: string) => request<T>("GET", path);
const post = <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? null);
const put = <T>(path: string, body: unknown) => request<T>("PUT", path, body);
const del = (path: string) => request<void>("DELETE", path);

export interface Note {
  id: number;
  uuid: string;
  body: string;
  created_at: string;
  updated_at: string;
  time_stamp: string;
  tags: string[];
  references: string[];
}

export interface Reference {
  id: number;
  name: string;
}

export interface Config {
  default_tags: string[];
  sync_folder: string;
  sync_adapter: string;
  sync_local_path: string;
  autosync_debounce_ms: number;
}

export interface Session {
  tags: string[];
  references: string[];
}

export interface PinsResponse {
  notes: Note[];
  updated_at: string;
}

export const api = {
  health: () => get<{ status: string }>("/health"),
  notes: {
    list: (params: { q?: string; tag?: string; reference?: string } = {}) => {
      const qs = new URLSearchParams();
      if (params.q) qs.set("q", params.q);
      if (params.tag) qs.set("tag", params.tag);
      if (params.reference) qs.set("reference", params.reference);
      const suffix = qs.toString() ? `?${qs}` : "";
      return get<Note[]>(`/notes${suffix}`);
    },
    create: (body: string, tags: string[] = [], references: string[] = []) =>
      post<Note>("/notes", { body, tags, references }),
    update: (id: number, body: string, tags: string[] = [], references: string[] = []) =>
      put<Note>(`/notes/${id}`, { body, tags, references }),
    delete: (id: number) => del(`/notes/${id}`),
  },
  tags: {
    list: () => get<string[]>("/tags"),
  },
  references: {
    list: () => get<Reference[]>("/references"),
  },
  config: {
    get: () => get<Config>("/config"),
    update: (payload: Partial<Config>) => put<Config>("/config", payload),
  },
  session: {
    get: () => get<Session>("/session"),
    set: (tags: string[], references: string[]) =>
      put<Session>("/session", { tags, references }),
    clear: () => del("/session"),
  },
  sync: {
    run:  () => post<{ message: string; needs_auth: boolean }>("/sync"),
    push: () => post<{ message: string; needs_auth: boolean }>("/sync/push"),
    pull: () => post<{ message: string; needs_auth: boolean }>("/sync/pull"),
  },
  pins: {
    list: () => get<PinsResponse>("/pins"),
    save: (uuids: string[]) => put<PinsResponse>("/pins", { uuids }),
  },
  auth: {
    googleConnect: () => post<{ message: string }>("/auth/google"),
  },
};
