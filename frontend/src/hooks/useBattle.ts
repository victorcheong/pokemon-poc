import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/api/client";
import type { Battle, BattleEvent, BattleFormat, Side, TurnAction } from "@/types";

/** Time between animated log lines, in ms. */
const STEP_MS = 650;

export interface BattleView {
  battle: Battle | null;
  /** Events already revealed to the player (animation head). */
  shownEvents: BattleEvent[];
  /** HP as currently displayed, keyed by "side:slot". Lags behind `battle` during animation. */
  displayedHp: Record<string, number>;
  /** "side:slot" of the Pokémon hit by the most recent damage event, for the shake animation. */
  hitKey: string | null;
  busy: boolean;
  animating: boolean;
  /** True while waiting for the opposing trainer's decision. */
  thinking: boolean;
  error: string | null;
}

const EMPTY: BattleView = {
  battle: null, shownEvents: [], displayedHp: {}, hitKey: null,
  busy: false, animating: false, thinking: false, error: null,
};

export function hpKey(side: Side, slot: number) {
  return `${side}:${slot}`;
}

function snapshotHp(b: Battle): Record<string, number> {
  const out: Record<string, number> = {};
  b.player_team.forEach((p) => (out[hpKey("player", p.slot)] = p.current_hp));
  b.opponent_team.forEach((p) => (out[hpKey("opponent", p.slot)] = p.current_hp));
  return out;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function useBattle() {
  const [view, setView] = useState<BattleView>(EMPTY);
  const latest = useRef<Battle | null>(null);
  const runToken = useRef(0);

  useEffect(() => {
    latest.current = view.battle;
  }, [view.battle]);

  /** Replay a response's events one by one so HP bars drain in sync with the log. */
  const animate = useCallback(async (next: Battle, prev: Battle | null) => {
    const token = ++runToken.current;
    let hp = prev ? snapshotHp(prev) : snapshotHp(next);
    const playerActive = [...(prev?.player_active ?? next.player_active)];
    const opponentActive = [...(prev?.opponent_active ?? next.opponent_active)];

    // Show the new teams (moves/PP) immediately but keep the old active slots and HP.
    const base: Battle = { ...next, player_active: [...playerActive], opponent_active: [...opponentActive] };
    setView((v) => ({ ...v, battle: base, displayedHp: hp, animating: true, thinking: false }));

    for (const ev of next.events) {
      if (runToken.current !== token) return;
      if (ev.type === "switch" && ev.target_side && ev.target_slot != null && ev.target_position != null) {
        (ev.target_side === "player" ? playerActive : opponentActive)[ev.target_position] = ev.target_slot;
      }
      let hitKey: string | null = null;
      if ((ev.type === "damage" || ev.type === "heal" || ev.type === "faint") && ev.target_side && ev.target_slot != null && ev.hp_after != null) {
        const key = hpKey(ev.target_side, ev.target_slot);
        hp = { ...hp, [key]: ev.hp_after };
        if (ev.type === "damage" && ev.damage > 0) hitKey = key;
      }
      const pa = [...playerActive];
      const oa = [...opponentActive];
      setView((v) => ({
        ...v,
        shownEvents: [...v.shownEvents, ev],
        displayedHp: hp,
        hitKey,
        battle: v.battle ? { ...v.battle, player_active: pa, opponent_active: oa } : v.battle,
      }));
      const isTurnMarker = ev.type === "text" && ev.text.startsWith("Turn ");
      await sleep(isTurnMarker ? 200 : STEP_MS);
    }
    if (runToken.current !== token) return;
    setView((v) => ({ ...v, battle: next, displayedHp: snapshotHp(next), hitKey: null, animating: false, busy: false }));
  }, []);

  const start = useCallback(
    async (team: number[], trainerId: string | null, format: BattleFormat): Promise<boolean> => {
      setView({ ...EMPTY, busy: true });
      try {
        const battle = await api.createBattle(team, trainerId, format);
        await animate(battle, null);
        return true;
      } catch (e) {
        setView((v) => ({ ...v, busy: false, error: e instanceof Error ? e.message : String(e) }));
        return false;
      }
    },
    [animate],
  );

  const act = useCallback(
    async (actions: TurnAction[]) => {
      const prev = latest.current;
      if (!prev) return;
      const opponentActs = prev.phase === "choose_action";
      setView((v) => ({ ...v, busy: true, thinking: opponentActs, error: null }));
      try {
        const next = await api.takeTurn(prev.id, actions);
        await animate(next, prev);
      } catch (e) {
        setView((v) => ({ ...v, busy: false, thinking: false, error: e instanceof Error ? e.message : String(e) }));
      }
    },
    [animate],
  );

  const reset = useCallback(() => {
    runToken.current++;
    setView(EMPTY);
  }, []);

  return { ...view, start, act, reset };
}
