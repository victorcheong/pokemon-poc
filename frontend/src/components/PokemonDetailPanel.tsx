import { useEffect, useState } from "react";
import { api } from "@/api/client";
import type { PokemonDetail } from "@/types";
import { TypeBadge } from "./TypeBadge";

const STAT_LABELS: Record<keyof PokemonDetail["stats"], string> = {
  hp: "HP", attack: "Atk", defense: "Def", sp_attack: "SpA", sp_defense: "SpD", speed: "Spe",
};

export function PokemonDetailPanel({ id }: { id: number | null }) {
  const [detail, setDetail] = useState<PokemonDetail | null>(null);

  useEffect(() => {
    if (id == null) return;
    let cancelled = false;
    api.getPokemon(id).then((d) => !cancelled && setDetail(d)).catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (!detail) return <p style={{ color: "var(--ink-dim)" }}>Hover a Pokémon to inspect it.</p>;

  return (
    <div>
      <div className="detail">
        <img src={detail.sprites.artwork} alt={detail.name} />
        <div>
          <strong style={{ fontSize: "1.05rem" }}>{detail.name}</strong>
          <div style={{ color: "var(--ink-dim)", fontSize: "0.75rem" }}>{detail.classification}</div>
          <div style={{ display: "flex", gap: 4, margin: "0.4rem 0" }}>
            {detail.types.map((t) => <TypeBadge key={t} type={t} />)}
          </div>
          <div className="stats">
            {(Object.keys(STAT_LABELS) as (keyof typeof STAT_LABELS)[]).map((k) => (
              <StatRow key={k} label={STAT_LABELS[k]} value={detail.stats[k]} />
            ))}
          </div>
        </div>
      </div>
      <div className="moves">
        {detail.moves.map((m) => (
          <span key={m.name} style={{ background: m.color }} title={`${m.category} · ${m.power || "—"} power · ${m.accuracy || "—"}% acc`}>
            {m.name}
          </span>
        ))}
      </div>
      {detail.weaknesses.length > 0 && (
        <div style={{ marginTop: "0.6rem", fontSize: "0.75rem", color: "var(--ink-dim)" }}>
          Weak to: {detail.weaknesses.join(", ")}
        </div>
      )}
    </div>
  );
}

function StatRow({ label, value }: { label: string; value: number }) {
  return (
    <>
      <span style={{ color: "var(--ink-dim)", fontWeight: 700 }}>{label}</span>
      <div className="bar"><i style={{ width: `${Math.min(100, (value / 200) * 100)}%` }} /></div>
      <span>{value}</span>
    </>
  );
}
