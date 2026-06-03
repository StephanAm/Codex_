// Copyright (C) 2026 Stephan Marais
// SPDX-License-Identifier: AGPL-3.0-or-later

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

export interface InstanceKind {
  id: number;
  name: string;
  plural: string;
  description: string;
}

export interface Instance {
  id: number;
  name: string;
  description: string;
  type: InstanceKind;
  references: string[];
}

export interface AtlasNode {
  id: number;
  uuid: string;
  name: string;
  parent_id: number | null;
  position: number;
  has_page: boolean;
  created_at: string;
  updated_at: string;
}

export interface AtlasPage {
  id: number;
  uuid: string;
  node_id: number;
  title: string;
  body: string;
  created_at: string;
  updated_at: string;
  tags: string[];
  references: string[];
  dates: string[];
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
  instanceKinds: {
    list: () => get<InstanceKind[]>("/instance-kinds"),
    create: (name: string, plural = "", description = "") =>
      post<InstanceKind>("/instance-kinds", { name, plural, description }),
    update: (id: number, name: string, plural: string, description: string) =>
      put<InstanceKind>(`/instance-kinds/${id}`, { name, plural, description }),
    delete: (id: number) => del(`/instance-kinds/${id}`),
  },
  instances: {
    list: (instanceKindId?: number) => {
      const qs = instanceKindId != null ? `?instance_kind_id=${instanceKindId}` : "";
      return get<Instance[]>(`/instances${qs}`);
    },
    create: (name: string, instanceKindId: number, description = "", references: string[] = []) =>
      post<Instance>("/instances", { name, instance_kind_id: instanceKindId, description, references }),
    update: (id: number, name: string, instanceKindId: number, description: string, references: string[] = []) =>
      put<Instance>(`/instances/${id}`, { name, instance_kind_id: instanceKindId, description, references }),
    delete: (id: number) => del(`/instances/${id}`),
  },
  atlas: {
    nodes: {
      list: () => get<AtlasNode[]>("/atlas/nodes"),
      create: (name: string, parent_id: number | null = null, position = 0) =>
        post<AtlasNode>("/atlas/nodes", { name, parent_id, position }),
      update: (id: number, name: string) =>
        put<AtlasNode>(`/atlas/nodes/${id}`, { name }),
      delete: (id: number) => del(`/atlas/nodes/${id}`),
      move: (id: number, parent_id: number | null, position: number) =>
        put<AtlasNode>(`/atlas/nodes/${id}/move`, { parent_id, position }),
      reorder: (updates: Array<{ node_id: number; parent_id: number | null; position: number }>) =>
        post<void>("/atlas/nodes/reorder", { updates }),
    },
    pages: {
      get: (nodeId: number) => get<AtlasPage>(`/atlas/nodes/${nodeId}/page`),
      create: (nodeId: number, title: string, body = "", tags: string[] = [], references: string[] = [], date_annotation: string | null = null, date_granularity: string | null = null) =>
        post<AtlasPage>(`/atlas/nodes/${nodeId}/page`, { title, body, tags, references, date_annotation, date_granularity }),
      update: (nodeId: number, title: string, body: string, tags: string[] = [], references: string[] = [], date_annotation: string | null = null, date_granularity: string | null = null) =>
        put<AtlasPage>(`/atlas/nodes/${nodeId}/page`, { title, body, tags, references, date_annotation, date_granularity }),
      delete: (nodeId: number) => del(`/atlas/nodes/${nodeId}/page`),
    },
  },
};
