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
  entities: string[];
}

export interface Entity {
  id: number;
  name: string;
  entity_type: string | null;
}

export interface Config {
  default_tags: string[];
  sync_folder: string;
  sync_adapter: string;
  sync_local_path: string;
}

export interface Session {
  tags: string[];
  entities: string[];
}

export const api = {
  health: () => get<{ status: string }>("/health"),
  notes: {
    list: (params: { q?: string; tag?: string; entity?: string } = {}) => {
      const qs = new URLSearchParams();
      if (params.q) qs.set("q", params.q);
      if (params.tag) qs.set("tag", params.tag);
      if (params.entity) qs.set("entity", params.entity);
      const suffix = qs.toString() ? `?${qs}` : "";
      return get<Note[]>(`/notes${suffix}`);
    },
    create: (body: string, tags: string[] = [], entities: string[] = []) =>
      post<Note>("/notes", { body, tags, entities }),
    update: (id: number, body: string, tags: string[] = [], entities: string[] = []) =>
      put<Note>(`/notes/${id}`, { body, tags, entities }),
    delete: (id: number) => del(`/notes/${id}`),
  },
  tags: {
    list: () => get<string[]>("/tags"),
  },
  entities: {
    list: () => get<Entity[]>("/entities"),
  },
  config: {
    get: () => get<Config>("/config"),
    update: (payload: Partial<Config>) => put<Config>("/config", payload),
  },
  session: {
    get: () => get<Session>("/session"),
    set: (tags: string[], entities: string[]) =>
      put<Session>("/session", { tags, entities }),
    clear: () => del("/session"),
  },
  sync: {
    run: () => post<{ message: string }>("/sync"),
  },
};
