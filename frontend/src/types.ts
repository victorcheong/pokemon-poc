/** Mirrors the backend Pydantic schemas (app/schemas.py). */

export type PokemonType =
  | "normal" | "fire" | "water" | "grass" | "electric" | "ice" | "fighting" | "poison" | "ground"
  | "flying" | "psychic" | "bug" | "rock" | "ghost" | "dragon" | "dark" | "steel" | "fairy";

export type Side = "player" | "opponent";

export interface Sprites {
  artwork: string;
  front: string;
  back: string;
  icon: string;
}

export interface MoveOut {
  name: string;
  type: PokemonType;
  color: string;
  category: "physical" | "special" | "status";
  power: number;
  accuracy: number;
  pp: number;
  max_pp: number;
  priority: number;
  description: string;
}

export interface PokemonSummary {
  id: number;
  name: string;
  types: PokemonType[];
  colors: string[];
  generation: number;
  is_legendary: boolean;
  base_total: number;
  sprites: Sprites;
}

export interface PokemonDetail extends PokemonSummary {
  japanese_name: string;
  classification: string;
  abilities: string[];
  stats: Record<"hp" | "attack" | "defense" | "sp_attack" | "sp_defense" | "speed", number>;
  height_m: number | null;
  weight_kg: number | null;
  weaknesses: PokemonType[];
  resistances: PokemonType[];
  immunities: PokemonType[];
  moves: MoveOut[];
}

export interface PokemonPage {
  items: PokemonSummary[];
  total: number;
}

export interface Trainer {
  id: string;
  name: string;
  title: string;
  sprite_url: string;
  preferred_types: PokemonType[];
  difficulty: number;
  intro: string;
}

export interface BattlePokemon {
  slot: number;
  id: number;
  name: string;
  types: PokemonType[];
  colors: string[];
  level: number;
  max_hp: number;
  current_hp: number;
  fainted: boolean;
  stats: Record<string, number>;
  stages: Record<string, number>;
  moves: MoveOut[];
  sprites: Sprites;
}

export interface BagItem {
  id: string;
  name: string;
  description: string;
  count: number;
}

export type EventType =
  | "item" | "switch" | "move" | "damage" | "miss" | "stat_change" | "heal" | "faint" | "text" | "battle_end";

export interface BattleEvent {
  type: EventType;
  side: Side | null;
  text: string;
  move: string | null;
  move_type: PokemonType | null;
  move_color: string | null;
  damage: number;
  effectiveness: number | null;
  critical: boolean;
  hp_after: number | null;
  pokemon: string | null;
  slot: number | null;
  position: number | null;
  target_side: Side | null;
  target_slot: number | null;
  target_position: number | null;
}

export type BattleFormat = "single" | "double";

export type Phase = "choose_action" | "player_must_switch" | "finished";

export interface OpponentDecision {
  position: number;
  pokemon: string;
  taunt: string;
  reasoning: string;
  source: string;
}

export interface Battle {
  id: string;
  format: BattleFormat;
  turn: number;
  phase: Phase;
  winner: Side | null;
  trainer: Trainer;
  agent: string;
  player_team: BattlePokemon[];
  opponent_team: BattlePokemon[];
  /** Team slot per field position; -1 = empty position. */
  player_active: number[];
  opponent_active: number[];
  positions_to_replace: number[];
  player_items: BagItem[];
  events: BattleEvent[];
  opponent_decisions: OpponentDecision[];
}

export type TurnAction =
  | { kind: "move"; position: number; move_index: number; target_position: number | null }
  | { kind: "switch"; position: number; slot: number }
  | { kind: "item"; position: number; item: string };

export interface Advice {
  position: number;
  pokemon: string;
  action: TurnAction;
  summary: string;
  coach_line: string;
  reasoning: string;
  source: string;
}
