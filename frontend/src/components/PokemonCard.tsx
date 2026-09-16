import type { PokemonSummary } from "@/types";
import { TypeBadge } from "./TypeBadge";

interface Props {
  pokemon: PokemonSummary;
  selected: boolean;
  onToggle: (p: PokemonSummary) => void;
  onInspect: (p: PokemonSummary) => void;
}

export function PokemonCard({ pokemon, selected, onToggle, onInspect }: Props) {
  const [c1, c2 = c1] = pokemon.colors;
  return (
    <div
      className={`poke-card${selected ? " selected" : ""}`}
      style={{ "--c1": c1, "--c2": c2 } as React.CSSProperties}
      onClick={() => onToggle(pokemon)}
      onMouseEnter={() => onInspect(pokemon)}
      role="button"
      aria-pressed={selected}
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onToggle(pokemon)}
    >
      <span className="dex">#{String(pokemon.id).padStart(3, "0")}</span>
      {pokemon.is_legendary && <span className="legend" title="Legendary">★</span>}
      <img src={pokemon.sprites.artwork} alt={pokemon.name} loading="lazy" />
      <div className="name">{pokemon.name}</div>
      <div className="types">
        {pokemon.types.map((t) => (
          <TypeBadge key={t} type={t} />
        ))}
      </div>
    </div>
  );
}
