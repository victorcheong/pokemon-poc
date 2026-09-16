import type { Battle } from "@/types";
import { agentLabel } from "./BattleScreen";

interface Props {
  battle: Battle;
  onRematch: () => void;
  onNewTeam: () => void;
}

export function ResultScreen({ battle, onRematch, onNewTeam }: Props) {
  const won = battle.winner === "player";
  const survivor = battle.player_team.find((p) => !p.fainted) ?? battle.player_team[0];
  const foe = battle.opponent_team.find((p) => !p.fainted) ?? battle.opponent_team[0];
  return (
    <section className={`panel result ${won ? "win" : "lose"}`}>
      <h1>{won ? "VICTORY!" : "DEFEAT…"}</h1>
      <div>
        <img src={won ? survivor.sprites.front : battle.trainer.sprite_url} alt="" />
        {!won && <img src={foe.sprites.front} alt={foe.name} />}
      </div>
      <p className="quote">
        {won
          ? `${battle.trainer.name}: "...You're stronger than I thought. Well fought."`
          : `${battle.trainer.name}: "${battle.opponent_decisions[0]?.taunt ?? "Come back when you're ready."}"`}
      </p>
      <p style={{ color: "var(--ink-dim)" }}>
        {battle.format === "double" ? "Double battle" : "Single battle"} · {battle.turn} turns · opponent: {agentLabel(battle.agent)}
      </p>
      <div className="action-row" style={{ justifyContent: "center", marginTop: "1rem" }}>
        <button className="btn" onClick={onRematch}>Rematch</button>
        <button className="btn secondary" onClick={onNewTeam}>New team</button>
      </div>
    </section>
  );
}
