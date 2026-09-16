import { useEffect, useMemo, useState } from "react";
import { api } from "@/api/client";
import type { BattleFormat, PokemonSummary, PokemonType } from "@/types";
import { ALL_TYPES } from "./TypeBadge";
import { PokemonCard } from "./PokemonCard";
import { PokemonDetailPanel } from "./PokemonDetailPanel";

const MAX_TEAM = 4;

interface Props {
  team: PokemonSummary[];
  onChange: (team: PokemonSummary[]) => void;
  format: BattleFormat;
  onFormatChange: (f: BattleFormat) => void;
  onNext: () => void;
}

export function TeamSelect({ team, onChange, format, onFormatChange, onNext }: Props) {
  const [all, setAll] = useState<PokemonSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [type, setType] = useState<PokemonType | "">("");
  const [gen, setGen] = useState<number | "">("");
  const [legendary, setLegendary] = useState(true);
  const [inspect, setInspect] = useState<number | null>(null);

  useEffect(() => {
    api
      .listPokemon({ limit: 1000 })
      .then((page) => setAll(page.items))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const visible = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return all.filter(
      (p) =>
        (!needle || p.name.toLowerCase().includes(needle) || String(p.id) === needle) &&
        (!type || p.types.includes(type)) &&
        (!gen || p.generation === gen) &&
        (legendary || !p.is_legendary),
    );
  }, [all, q, type, gen, legendary]);

  const toggle = (p: PokemonSummary) => {
    if (team.some((t) => t.id === p.id)) onChange(team.filter((t) => t.id !== p.id));
    else if (team.length < MAX_TEAM) onChange([...team, p]);
  };

  const randomTeam = () => {
    const pool = visible.length >= MAX_TEAM ? visible : all;
    const picks: PokemonSummary[] = [];
    while (picks.length < MAX_TEAM && pool.length) {
      const p = pool[Math.floor(Math.random() * pool.length)];
      if (!picks.some((x) => x.id === p.id)) picks.push(p);
    }
    onChange(picks);
  };

  return (
    <div className="select-layout">
      <section className="panel">
        <h2>Choose your team (up to {MAX_TEAM})</h2>
        <div className="filters">
          <input placeholder="Search by name or #" value={q} onChange={(e) => setQ(e.target.value)} />
          <select value={type} onChange={(e) => setType(e.target.value as PokemonType | "")}>
            <option value="">All types</option>
            {ALL_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <select value={gen} onChange={(e) => setGen(e.target.value ? Number(e.target.value) : "")}>
            <option value="">All gens</option>
            {[1, 2, 3, 4, 5, 6, 7].map((g) => (
              <option key={g} value={g}>Gen {g}</option>
            ))}
          </select>
          <label>
            <input type="checkbox" checked={legendary} onChange={(e) => setLegendary(e.target.checked)} /> Legendary
          </label>
        </div>
        {error && <div className="error">{error}</div>}
        {loading ? (
          <div className="loading"><span className="spinner" />Loading Pokédex…</div>
        ) : (
          <div className="poke-grid">
            {visible.map((p) => (
              <PokemonCard
                key={p.id}
                pokemon={p}
                selected={team.some((t) => t.id === p.id)}
                onToggle={toggle}
                onInspect={(x) => setInspect(x.id)}
              />
            ))}
          </div>
        )}
      </section>

      <aside className="panel team-panel">
        <h2>Your party</h2>
        <div className="segmented" role="radiogroup" aria-label="Battle format">
          <button className={format === "single" ? "on" : ""} onClick={() => onFormatChange("single")}>Single 1v1</button>
          <button className={format === "double" ? "on" : ""} onClick={() => onFormatChange("double")}>Double 2v2</button>
        </div>
        <p className="hint">{format === "double" ? "Two Pokémon fight at once. The first two in your party start on the field." : "One Pokémon at a time; the rest wait on the bench."}</p>
        <div className="slots">
          {Array.from({ length: MAX_TEAM }).map((_, i) => {
            const p = team[i];
            return p ? (
              <div key={p.id} className="team-slot filled" style={{ "--c1": p.colors[0] } as React.CSSProperties}>
                <img src={p.sprites.front} alt={p.name} onError={(e) => (e.currentTarget.src = p.sprites.icon)} />
                <div className="info">
                  <strong>{p.name}</strong>
                  <small>{p.types.join(" / ")} · BST {p.base_total}</small>
                </div>
                <button className="remove" onClick={() => toggle(p)} aria-label={`Remove ${p.name}`}>✕</button>
              </div>
            ) : (
              <div key={`empty-${i}`} className="team-slot"><span className="empty">EMPTY SLOT</span></div>
            );
          })}
        </div>
        <div className="action-row">
          <button className="btn secondary" onClick={randomTeam}>Random</button>
          <button className="btn" disabled={team.length < (format === "double" ? 2 : 1)} onClick={onNext}>
            Pick opponent →
          </button>
        </div>
        <hr style={{ border: 0, borderTop: "1px solid rgba(255,255,255,0.1)", margin: "1rem 0" }} />
        <PokemonDetailPanel id={inspect ?? team[0]?.id ?? null} />
      </aside>
    </div>
  );
}
