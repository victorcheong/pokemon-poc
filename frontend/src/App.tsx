import { useState } from "react";
import type { BattleFormat, PokemonSummary } from "@/types";
import { useBattle } from "@/hooks/useBattle";
import { TeamSelect } from "@/components/TeamSelect";
import { TrainerSelect } from "@/components/TrainerSelect";
import { BattleScreen } from "@/components/BattleScreen";
import { ResultScreen } from "@/components/ResultScreen";

type Screen = "team" | "trainer" | "battle" | "result";

const STEPS: { id: Screen; label: string }[] = [
  { id: "team", label: "1 TEAM" },
  { id: "trainer", label: "2 OPPONENT" },
  { id: "battle", label: "3 BATTLE" },
  { id: "result", label: "4 RESULT" },
];

export default function App() {
  const [screen, setScreen] = useState<Screen>("team");
  const [team, setTeam] = useState<PokemonSummary[]>([]);
  const [trainerId, setTrainerId] = useState<string | null>(null);
  const [format, setFormat] = useState<BattleFormat>("single");
  const battle = useBattle();

  const startBattle = async () => {
    const ok = await battle.start(team.map((p) => p.id), trainerId, format);
    if (ok) setScreen("battle");
  };

  const stepIndex = STEPS.findIndex((s) => s.id === screen);

  return (
    <div className="app">
      <header className="topbar">
        <h1>POKÉMON BATTLE ARENA</h1>
        <nav className="steps" aria-label="Progress">
          {STEPS.map((s, i) => (
            <span key={s.id} className={i === stepIndex ? "active" : i < stepIndex ? "done" : ""}>{s.label}</span>
          ))}
        </nav>
      </header>

      {screen === "team" && (
        <TeamSelect team={team} onChange={setTeam} format={format} onFormatChange={setFormat} onNext={() => setScreen("trainer")} />
      )}

      {screen === "trainer" && (
        <TrainerSelect
          selected={trainerId}
          onSelect={setTrainerId}
          onBack={() => setScreen("team")}
          onStart={startBattle}
          starting={battle.busy}
          error={battle.error}
        />
      )}

      {screen === "battle" && battle.battle && (
        <BattleScreen
          battle={battle.battle}
          shownEvents={battle.shownEvents}
          displayedHp={battle.displayedHp}
          hitKey={battle.hitKey}
          busy={battle.busy}
          animating={battle.animating}
          thinking={battle.thinking}
          error={battle.error}
          onAct={battle.act}
          onFinish={() => setScreen("result")}
        />
      )}

      {screen === "result" && battle.battle && (
        <ResultScreen
          battle={battle.battle}
          onRematch={() => { battle.reset(); setScreen("trainer"); }}
          onNewTeam={() => { battle.reset(); setTeam([]); setScreen("team"); }}
        />
      )}
    </div>
  );
}
