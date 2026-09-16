import { useEffect, useState } from "react";
import { api } from "@/api/client";
import type { Trainer } from "@/types";
import { TypeBadge } from "./TypeBadge";

interface Props {
  selected: string | null; // null = random
  onSelect: (id: string | null) => void;
  onBack: () => void;
  onStart: () => void;
  starting: boolean;
  error: string | null;
}

export function TrainerSelect({ selected, onSelect, onBack, onStart, starting, error }: Props) {
  const [trainers, setTrainers] = useState<Trainer[]>([]);

  useEffect(() => {
    api.listTrainers().then(setTrainers).catch(() => setTrainers([]));
  }, []);

  return (
    <section className="panel">
      <h2>Who do you want to battle?</h2>
      <div className="trainer-grid">
        <div className={`trainer-card random${selected === null ? " selected" : ""}`} onClick={() => onSelect(null)}>
          <div className="q">?</div>
          <div className="tname">RANDOM</div>
          <div className="ttitle">Surprise me</div>
          <div className="stars">★ ~ ★</div>
        </div>
        {trainers.map((t) => (
          <div
            key={t.id}
            className={`trainer-card${selected === t.id ? " selected" : ""}`}
            onClick={() => onSelect(t.id)}
            title={t.intro}
          >
            <img src={t.sprite_url} alt={t.name} />
            <div className="tname">{t.name.toUpperCase()}</div>
            <div className="ttitle">{t.title}</div>
            <div className="stars">{"★".repeat(t.difficulty)}{"☆".repeat(5 - t.difficulty)}</div>
            <div className="types">
              {t.preferred_types.length ? t.preferred_types.map((pt) => <TypeBadge key={pt} type={pt} />) : <small style={{ color: "var(--ink-dim)" }}>Mixed team</small>}
            </div>
          </div>
        ))}
      </div>
      {error && <div className="error">{error}</div>}
      <div className="action-row" style={{ marginTop: "1rem" }}>
        <button className="btn secondary" onClick={onBack} disabled={starting}>← Back</button>
        <button className="btn danger" onClick={onStart} disabled={starting}>
          {starting ? "Starting…" : "Battle!"}
        </button>
      </div>
    </section>
  );
}
