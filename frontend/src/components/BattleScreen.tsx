import { useEffect, useMemo, useRef, useState } from "react";
import type { Battle, BattleEvent, BattlePokemon, MoveOut, TurnAction } from "@/types";
import { hpKey } from "@/hooks/useBattle";
import { api } from "@/api/client";
import { ApiActivity } from "./ApiActivity";
import type { Advice } from "@/types";
import { HpBox } from "./HpBar";
import { TypeBadge } from "./TypeBadge";

interface Props {
  battle: Battle;
  shownEvents: BattleEvent[];
  displayedHp: Record<string, number>;
  hitKey: string | null;
  busy: boolean;
  animating: boolean;
  thinking: boolean;
  error: string | null;
  onAct: (actions: TurnAction[]) => void;
  onFinish: () => void;
}

type Chart = Record<string, number>;

/** Label a move by its effectiveness against a foe, using the public Pokédex weaknesses. */
function effectivenessLabel(move: MoveOut, chart: Chart | undefined) {
  if (move.category === "status" || !chart) return null;
  const mult = chart[move.type] ?? 1;
  if (mult === 0) return { cls: "none", text: "No effect" };
  if (mult > 1) return { cls: "super", text: `×${mult}` };
  if (mult < 1) return { cls: "weak", text: `×${mult}` };
  return null;
}

export function agentLabel(source: string): string {
  switch (source) {
    case "claude":
      return "Powered by Claude API";
    case "claude_code":
      return "Powered by Claude Code";
    default:
      return "Heuristic AI";
  }
}

/** Pokémon on the field for one side, in position order (null = empty position). */
function fielded(team: BattlePokemon[], active: number[]): (BattlePokemon | null)[] {
  return active.map((slot) => (slot >= 0 ? team[slot] : null));
}

export function BattleScreen(props: Props) {
  const { battle, shownEvents, displayedHp, hitKey, busy, animating, thinking, error, onAct, onFinish } = props;
  const isDouble = battle.format === "double";
  const mine = fielded(battle.player_team, battle.player_active);
  const foes = fielded(battle.opponent_team, battle.opponent_active);
  const livingFoes = foes.map((p, pos) => ({ p, pos })).filter((x) => x.p && !x.p.fainted) as { p: BattlePokemon; pos: number }[];

  const [mode, setMode] = useState<"menu" | "fight" | "switch" | "bag">("menu");
  const [advice, setAdvice] = useState<Advice | null>(null);
  const [advising, setAdvising] = useState(false);
  const [adviceError, setAdviceError] = useState<string | null>(null);
  const [queued, setQueued] = useState<TurnAction[]>([]); // actions chosen so far this turn (doubles)
  const [pendingMove, setPendingMove] = useState<number | null>(null); // move awaiting a target
  const logRef = useRef<HTMLDivElement>(null);
  const [charts, setCharts] = useState<Record<number, Chart>>({});

  const mustSwitch = battle.phase === "player_must_switch";
  const finished = battle.phase === "finished" && !animating;
  const canAct = !busy && !animating && battle.phase !== "finished";

  // Positions the player still has to decide for this turn.
  const positionsToAct = mustSwitch
    ? battle.positions_to_replace
    : mine.map((p, pos) => ({ p, pos })).filter((x) => x.p && !x.p.fainted).map((x) => x.pos);
  const decided = new Set(queued.map((a) => a.position));
  const currentPos = positionsToAct.find((pos) => !decided.has(pos)) ?? null;
  const me = currentPos != null ? mine[currentPos] : null;

  // Pull each foe's weaknesses from the public Pokédex endpoint to annotate move buttons.
  useEffect(() => {
    const ids = foes.filter((f): f is BattlePokemon => !!f).map((f) => f.id);
    ids.forEach((id) => {
      if (charts[id]) return;
      api
        .getPokemon(id)
        .then((d) => {
          const chart: Chart = {};
          d.weaknesses.forEach((t) => (chart[t] = 2));
          d.resistances.forEach((t) => (chart[t] = 0.5));
          d.immunities.forEach((t) => (chart[t] = 0));
          setCharts((c) => ({ ...c, [id]: chart }));
        })
        .catch(() => undefined);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [battle.opponent_active.join(","), battle.opponent_team.map((p) => p.id).join(",")]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [shownEvents.length]);

  // Reset per-turn choices whenever a new decision phase begins.
  useEffect(() => {
    if (animating) return;
    setQueued([]);
    setPendingMove(null);
    setAdvice(null);
    setAdviceError(null);
    setMode(mustSwitch ? "switch" : "menu");
  }, [battle.turn, battle.phase, animating, mustSwitch]);

  const submit = (actions: TurnAction[]) => {
    setQueued([]);
    setPendingMove(null);
    setAdvice(null);
    onAct(actions);
  };

  const askCoach = async () => {
    if (currentPos == null) return;
    setAdvising(true);
    setAdviceError(null);
    try {
      setAdvice(await api.getAdvice(battle.id, currentPos));
    } catch (e) {
      setAdviceError(e instanceof Error ? e.message : String(e));
    } finally {
      setAdvising(false);
    }
  };

  /** Queue an action for the current position; submit once every position has one. */
  const queue = (action: TurnAction) => {
    const next = [...queued, action];
    const remaining = positionsToAct.filter((pos) => !next.some((a) => a.position === pos));
    if (remaining.length === 0) submit(next);
    else {
      setQueued(next);
      setPendingMove(null);
      setAdvice(null);
      setMode(mustSwitch ? "switch" : "menu");
    }
  };

  const chooseMove = (moveIndex: number) => {
    if (currentPos == null) return;
    if (isDouble && livingFoes.length > 1 && me?.moves[moveIndex].category !== "status") {
      setPendingMove(moveIndex); // ask for a target
      return;
    }
    queue({ kind: "move", position: currentPos, move_index: moveIndex, target_position: livingFoes[0]?.pos ?? null });
  };

  const lastLine = shownEvents[shownEvents.length - 1]?.text ?? "";
  const prompt = thinking
    ? `${battle.trainer.name} is thinking…`
    : pendingMove != null && me
      ? `${me.name}'s ${me.moves[pendingMove].name} — choose a target`
      : mustSwitch && me
        ? `${me.name} fainted! Choose a replacement.`
        : mode === "bag" && me
          ? `Use an item on ${me.name}?`
          : me
            ? `What will ${me.name} do?`
            : lastLine;

  const decisions = battle.opponent_decisions;
  const bubbles = useMemo(
    () => (decisions.length ? decisions : [{ position: 0, pokemon: "", taunt: battle.trainer.intro, reasoning: "", source: battle.agent }]),
    [decisions, battle.trainer.intro, battle.agent],
  );

  // Slots already promised to another position this turn cannot be chosen again.
  const reservedSlots = new Set(queued.filter((a) => a.kind === "switch").map((a) => (a as { slot: number }).slot));

  return (
    <div className="battle">
      <div>
        <div className={`arena${isDouble ? " double" : ""}`}>
          <div className="cloud c1" />
          <div className="cloud c2" />
          {foes.map((_, pos) => (
            <div key={`oppslot-${pos}`} className={`platform opp p${pos}`} />
          ))}
          {mine.map((_, pos) => (
            <div key={`myslot-${pos}`} className={`platform me p${pos}`} />
          ))}
          {foes.map((foe, pos) =>
            foe ? (
              <img
                key={`opp-${pos}-${foe.id}`}
                className={`sprite opp p${pos}${hitKey === hpKey("opponent", foe.slot) ? " hit" : ""}${(displayedHp[hpKey("opponent", foe.slot)] ?? foe.current_hp) <= 0 ? " fainted" : ""}`}
                src={foe.sprites.front}
                alt={foe.name}
                onError={(e) => (e.currentTarget.src = foe.sprites.artwork)}
              />
            ) : null,
          )}
          {mine.map((p, pos) =>
            p ? (
              <img
                key={`me-${pos}-${p.id}`}
                className={`sprite me p${pos}${hitKey === hpKey("player", p.slot) ? " hit" : ""}${(displayedHp[hpKey("player", p.slot)] ?? p.current_hp) <= 0 ? " fainted" : ""}${currentPos === pos && canAct ? " choosing" : ""}`}
                src={p.sprites.back}
                alt={p.name}
                onError={(e) => (e.currentTarget.src = p.sprites.artwork)}
              />
            ) : null,
          )}
          <div className={`flash${hitKey ? " on" : ""}`} key={shownEvents.length} />
          <div className="hud-stack opp">
            {foes.map((foe, pos) =>
              foe ? (
                <HpBox key={`hud-opp-${pos}`} side="opponent" pokemon={foe} hp={displayedHp[hpKey("opponent", foe.slot)] ?? foe.current_hp} team={pos === 0 ? battle.opponent_team : []} />
              ) : null,
            )}
          </div>
          <div className="hud-stack me">
            {mine.map((p, pos) =>
              p ? (
                <HpBox key={`hud-me-${pos}`} side="player" pokemon={p} hp={displayedHp[hpKey("player", p.slot)] ?? p.current_hp} team={pos === 0 ? battle.player_team : []} highlight={currentPos === pos && canAct} />
              ) : null,
            )}
          </div>
        </div>

        <div className="controls">
          <div className="dialog">
            {prompt}
            {!animating && !thinking && <span className="caret">▼</span>}
          </div>

          {error && <div className="error">{error}</div>}

          {advice && (
            <div className="coach">
              <div className="coach-head">
                <span className="coach-icon">🎓</span>
                <div>
                  <div className="coach-title">Coach suggests: <strong>{advice.summary}</strong></div>
                  <div className="coach-line">{advice.coach_line}</div>
                </div>
                <span className={`agent-tag ${advice.source}`}>{agentLabel(advice.source)}</span>
              </div>
              <p className="coach-reason">{advice.reasoning}</p>
              <div className="action-row">
                <button className="btn" disabled={!canAct} onClick={() => queue(advice.action)}>Do it</button>
                <button className="btn secondary" onClick={() => setAdvice(null)}>Ignore</button>
              </div>
            </div>
          )}
          {adviceError && <div className="error">Coach unavailable: {adviceError}</div>}

          {finished ? (
            <div className="action-row">
              <button className="btn" onClick={onFinish}>See results →</button>
            </div>
          ) : mode === "menu" && !mustSwitch && me ? (
            <div className="main-menu">
              <button className="menu-btn fight" disabled={!canAct} onClick={() => setMode("fight")}>
                <span>FIGHT</span><small>Choose a move</small>
              </button>
              <button className="menu-btn pokemon" disabled={!canAct || battle.player_team.length <= mine.filter(Boolean).length} onClick={() => setMode("switch")}>
                <span>POKÉMON</span><small>Switch out</small>
              </button>
              <button className="menu-btn bag" disabled={!canAct || battle.player_items.every((i) => i.count === 0)} onClick={() => setMode("bag")}>
                <span>BAG</span><small>{battle.player_items.reduce((n, i) => n + i.count, 0)} items</small>
              </button>
              <button className="menu-btn run" disabled={busy} onClick={onFinish}>
                <span>RUN</span><small>Forfeit</small>
              </button>
              <button className="menu-btn coach" disabled={!canAct || advising} onClick={askCoach}>
                <span>{advising ? "THINKING…" : "ASK COACH"}</span><small>Agent recommends a move</small>
              </button>
              {queued.length > 0 && (
                <button className="menu-btn undo" disabled={!canAct} onClick={() => setQueued([])}>
                  <span>UNDO</span><small>Redo position {queued[0]?.position}</small>
                </button>
              )}
            </div>
          ) : mode === "bag" && me ? (
            <>
              <div className="switch-panel">
                {battle.player_items.map((it) => (
                  <button
                    key={it.id}
                    className="switch-btn item"
                    style={{ "--c": "var(--accent)" } as React.CSSProperties}
                    disabled={!canAct || it.count === 0 || me.current_hp >= me.max_hp}
                    onClick={() => queue({ kind: "item", position: currentPos!, item: it.id })}
                    title={it.description}
                  >
                    <span className="item-icon">🧪</span>
                    <span>
                      <strong>{it.name} ×{it.count}</strong>
                      <small>{it.description}</small>
                    </span>
                  </button>
                ))}
              </div>
              {me.current_hp >= me.max_hp && <p className="hint">{me.name}'s HP is already full.</p>}
              <div className="action-row">
                <button className="btn secondary" onClick={() => setMode("menu")}>← Back</button>
              </div>
            </>
          ) : pendingMove != null && me ? (
            <>
              <div className="target-panel">
                {livingFoes.map(({ p, pos }) => {
                  const eff = effectivenessLabel(me.moves[pendingMove], charts[p.id]);
                  return (
                    <button
                      key={pos}
                      className="switch-btn"
                      style={{ "--c": p.colors[0] } as React.CSSProperties}
                      disabled={!canAct}
                      onClick={() => queue({ kind: "move", position: currentPos!, move_index: pendingMove, target_position: pos })}
                    >
                      <img src={p.sprites.icon} alt={p.name} />
                      <span>
                        <strong>{p.name}</strong>
                        <small>{Math.round(((displayedHp[hpKey("opponent", p.slot)] ?? p.current_hp) / p.max_hp) * 100)}% HP{eff ? ` · ${eff.text}` : ""}</small>
                      </span>
                    </button>
                  );
                })}
              </div>
              <div className="action-row">
                <button className="btn secondary" onClick={() => setPendingMove(null)}>← Back</button>
              </div>
            </>
          ) : mode === "fight" && !mustSwitch && me ? (
            <>
              <div className="moves">
                {me.moves.map((m, i) => {
                  const eff = livingFoes.length === 1 ? effectivenessLabel(m, charts[livingFoes[0].p.id]) : null;
                  const suggested = advice?.action.kind === "move" && advice.action.move_index === i;
                  return (
                    <button
                      key={m.name}
                      className={`move-btn${suggested ? " suggested" : ""}`}
                      style={{ "--c": m.color } as React.CSSProperties}
                      disabled={!canAct || m.pp <= 0}
                      onClick={() => chooseMove(i)}
                      title={m.description || `${m.category} move`}
                    >
                      <span className="mname">{m.name}</span>
                      <span className="meta">
                        <span>{m.type.toUpperCase()}</span>
                        <span>{m.category === "status" ? "STATUS" : `PWR ${m.power}`}</span>
                        <span>{m.accuracy ? `ACC ${m.accuracy}` : "ACC —"}</span>
                        <span>PP {m.pp}/{m.max_pp}</span>
                        {eff && <span className={`eff ${eff.cls}`}>{eff.text}</span>}
                      </span>
                    </button>
                  );
                })}
              </div>
              <div className="action-row">
                <button className="btn secondary" disabled={!canAct} onClick={() => setMode("menu")}>← Back</button>
              </div>
            </>
          ) : (
            <>
              <div className="switch-panel">
                {battle.player_team.map((p) => {
                  const onField = battle.player_active.includes(p.slot);
                  const reserved = reservedSlots.has(p.slot);
                  return (
                    <button
                      key={p.slot}
                      className={`switch-btn${p.fainted ? " fainted" : ""}${onField ? " active" : ""}`}
                      style={{ "--c": p.colors[0] } as React.CSSProperties}
                      disabled={!canAct || p.fainted || onField || reserved || currentPos == null}
                      onClick={() => queue({ kind: "switch", position: currentPos!, slot: p.slot })}
                    >
                      <img src={p.sprites.icon} alt={p.name} />
                      <span>
                        <strong>{p.name}</strong>
                        <small>{p.fainted ? "Fainted" : `${p.current_hp}/${p.max_hp} HP`}{onField ? " · on field" : reserved ? " · chosen" : ""}</small>
                      </span>
                    </button>
                  );
                })}
              </div>
              {!mustSwitch && (
                <div className="action-row">
                  <button className="btn secondary" disabled={!canAct} onClick={() => setMode("menu")}>← Back</button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <aside className="sidebar">
        <div className="panel trainer-box">
          <img src={battle.trainer.sprite_url} alt={battle.trainer.name} />
          <div>
            <div className="tname">{battle.trainer.name.toUpperCase()}</div>
            <div className="ttitle">{battle.trainer.title}{isDouble ? " · Double battle" : ""}</div>
            {thinking ? (
              <div className="bubble thinking">…</div>
            ) : (
              bubbles.map((d, i) => (
                <div key={i} className="bubble-group">
                  <div className="bubble">
                    {d.pokemon && <span className="who">{d.pokemon}: </span>}
                    {d.taunt}
                  </div>
                  <span className={`agent-tag ${d.source}`}>{agentLabel(d.source)}</span>
                  {d.reasoning && (
                    <details className="reasoning">
                      <summary>Reasoning</summary>
                      {d.reasoning}
                    </details>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        <div className="panel">
          <h2>Battle log</h2>
          <div className="log" ref={logRef}>
            {shownEvents.map((e, i) => (
              <div key={i} className={logClass(e)}>{e.text}</div>
            ))}
          </div>
        </div>

        <ApiActivity />

        <div className="panel">
          <h2>Opponent's team</h2>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            {battle.opponent_team.map((p) => (
              <div key={p.slot} style={{ textAlign: "center", opacity: p.fainted ? 0.4 : 1, filter: p.fainted ? "grayscale(1)" : "none" }} title={p.name}>
                <img src={p.sprites.icon} alt={p.name} style={{ width: 56, height: 56 }} />
                <div style={{ display: "flex", gap: 2, justifyContent: "center" }}>
                  {p.types.map((t) => <TypeBadge key={t} type={t} />)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}

function logClass(e: BattleEvent): string {
  const cls = ["entry"];
  if (e.side) cls.push(e.side);
  if (e.type === "text" && e.text.startsWith("Turn ")) cls.push("turn");
  if (e.text === "A critical hit!") cls.push("crit");
  if (e.text === "It's super effective!") cls.push("super");
  if (e.type === "faint" || e.type === "battle_end") cls.push("faint");
  return cls.join(" ");
}
