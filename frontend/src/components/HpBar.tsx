import type { BattlePokemon } from "@/types";

interface Props {
  side: "player" | "opponent";
  pokemon: BattlePokemon;
  hp: number;
  team: BattlePokemon[];
  highlight?: boolean;
}

const STAGE_LABEL: Record<string, string> = {
  attack: "ATK", defense: "DEF", sp_attack: "SPA", sp_defense: "SPD", speed: "SPE",
};

export function HpBox({ side, pokemon, hp, team, highlight }: Props) {
  const pct = Math.max(0, Math.min(100, (hp / pokemon.max_hp) * 100));
  const color = pct > 50 ? "var(--hp-green)" : pct > 20 ? "var(--hp-yellow)" : "var(--hp-red)";
  const stages = Object.entries(pokemon.stages).filter(([, v]) => v !== 0);
  return (
    <div className={`hud ${side === "player" ? "me" : "opp"}${highlight ? " highlight" : ""}`}>
      <div className="row">
        <span>{pokemon.name}</span>
        <span className="lvl">Lv{pokemon.level}</span>
      </div>
      <div className="hpbar">
        <span className="label">HP</span>
        <div className="track">
          <div className="fill" style={{ width: `${pct}%`, backgroundColor: color }} />
        </div>
      </div>
      {side === "player" && <div className="hpnum">{Math.max(0, Math.round(hp))} / {pokemon.max_hp}</div>}
      {team.length > 0 && (
        <div className="balls" aria-label="Team status">
          {team.map((p) => (
            <span key={p.slot} className={`ball${p.fainted ? " out" : ""}`} title={p.name} />
          ))}
        </div>
      )}
      {stages.length > 0 && (
        <div className="stages">
          {stages.map(([k, v]) => (
            <span key={k} className={v < 0 ? "down" : ""}>
              {STAGE_LABEL[k] ?? k} {v > 0 ? `+${v}` : v}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
