import type { Advice, Battle, BattleFormat, PokemonDetail, PokemonPage, PokemonType, Trainer, TurnAction } from "@/types";

export const BASE = import.meta.env.VITE_API_BASE ?? "/api";

/** One line per HTTP call, so the UI can show exactly which endpoints were invoked. */
export interface ApiCall {
  id: number;
  method: string;
  path: string;
  status: number | null;
  ms: number;
  at: Date;
}

type Listener = (calls: ApiCall[]) => void;
const calls: ApiCall[] = [];
const listeners = new Set<Listener>();
let nextId = 1;

export function subscribeApiLog(fn: Listener): () => void {
  listeners.add(fn);
  fn([...calls]);
  return () => listeners.delete(fn);
}

function record(call: ApiCall) {
  calls.push(call);
  if (calls.length > 50) calls.shift();
  listeners.forEach((fn) => fn([...calls]));
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const started = performance.now();
  const method = init?.method ?? "GET";
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch (e) {
    record({ id: nextId++, method, path, status: null, ms: performance.now() - started, at: new Date() });
    throw e;
  }
  record({ id: nextId++, method, path, status: res.status, ms: performance.now() - started, at: new Date() });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
      else if (body.detail) detail = JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export interface PokemonQuery {
  q?: string;
  type?: PokemonType | "";
  generation?: number | "";
  include_legendary?: boolean;
  limit?: number;
  offset?: number;
}

export const api = {
  listPokemon(query: PokemonQuery = {}): Promise<PokemonPage> {
    const params = new URLSearchParams();
    if (query.q) params.set("q", query.q);
    if (query.type) params.set("type", query.type);
    if (query.generation) params.set("generation", String(query.generation));
    if (query.include_legendary === false) params.set("include_legendary", "false");
    params.set("limit", String(query.limit ?? 1000));
    if (query.offset) params.set("offset", String(query.offset));
    return request<PokemonPage>(`/pokemon?${params.toString()}`);
  },
  getPokemon(id: number): Promise<PokemonDetail> {
    return request<PokemonDetail>(`/pokemon/${id}`);
  },
  listTrainers(): Promise<Trainer[]> {
    return request<Trainer[]>("/trainers");
  },
  createBattle(team: number[], trainerId: string | null, format: BattleFormat): Promise<Battle> {
    return request<Battle>("/battles", {
      method: "POST",
      body: JSON.stringify({ team, trainer_id: trainerId, format }),
    });
  },
  getAdvice(battleId: string, position: number): Promise<Advice> {
    return request<Advice>(`/battles/${battleId}/advice`, {
      method: "POST",
      body: JSON.stringify({ position }),
    });
  },
  takeTurn(battleId: string, actions: TurnAction[]): Promise<Battle> {
    return request<Battle>(`/battles/${battleId}/turn`, {
      method: "POST",
      body: JSON.stringify({ actions }),
    });
  },
};
