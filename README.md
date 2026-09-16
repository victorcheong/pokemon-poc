# Pokémon Battle Arena

A dockerised **FastAPI** battle simulator built on the Kaggle
[Complete Pokémon Dataset](https://www.kaggle.com/datasets/rounakbanik/pokemon)
(801 Pokémon, Gen 1–7) with a **React** battle UI and a **Claude-powered opposing
trainer** that decides every move the opponent makes.

```
┌────────────────────┐   /api    ┌───────────────────────┐  claude -p (CLI) or  ┌───────────────┐
│ frontend (nginx)   │ ────────► │ backend (FastAPI)     │  Messages API        │ Claude        │
│ React + Vite + TS  │           │ dataset · battle      │ ───────────────────► │ (opposing     │
│ :8080              │           │ engine · agents :8000 │ ◄─── JSON decision   │  trainer AI)  │
│ Swagger: /api/docs │           │ Swagger: /api/docs    │                      │               │
└────────────────────┘           └───────────────────────┘                      └───────────────┘
```

## Features

1. **Choose your Pokémon** – browse all 801 with official artwork, search, type/generation
   filters, stat and move preview, and pick a party of up to four.
2. **Battle a trainer** – twelve opponents (Gym Leaders, Champions, Red) each with a themed team
   scaled to your party's strength; or pick *Random*. Play **single (1v1)** or **double (2v2)**
   battles; in doubles you choose a move and a target for each of your two Pokémon.
3. **Battle menu** – the classic **FIGHT / POKÉMON / BAG / RUN** menu. Moves are only shown
   after choosing Fight, so nothing fires by accident. The Bag holds Potions, a Hyper Potion
   and a Full Restore; using one takes the turn and heals before any move lands.
4. **Ask Coach** – an agent on *your* side. It reads the same kind of briefing as the opponent
   (from your point of view, including your bag) and recommends a move and target, a switch or
   an item, with its reasoning. "Do it" submits the recommendation; you can also ignore it.
5. **API activity panel** – the sidebar lists every endpoint the UI calls (method, path, status,
   latency) with a link to Swagger, so you can see the backend being used in real time.
6. **Agent-driven opponent** – each turn the trainer's decision (attack, set up, heal, or switch)
   is made by Claude from a numeric battle briefing. It answers with a validated JSON decision,
   an in-character taunt shown in a speech bubble, and its reasoning. **In a double battle each
   opponent Pokémon gets its own agent call**, run concurrently, so the two act independently.
   Claude can be reached through the **Claude Code CLI using your Claude subscription** (no API
   key) or the **Anthropic API**; with neither available a built-in heuristic trainer plays.

Battle rules: level 50, real damage formula (STAB, type effectiveness from the dataset's
`against_*` columns, criticals, damage roll), stat stages, priority moves, PP, switching,
forced replacement on faint. Movesets are generated from each Pokémon's typing and stat
profile because the dataset has no move data.

## Demo video

A recorded walkthrough of a full battle, with captions naming each API call as it happens:
[`demo/pokemon-battle-demo.mp4`](demo/pokemon-battle-demo.mp4) (2½ min). Re-record it any time
with `scripts/record_demo.py` (instructions in the file header).

## Quick start (Docker)

```bash
cp .env.example .env            # defaults to OPPONENT_AGENT=auto
docker compose up --build
```

Open <http://localhost:8080> to play. **Swagger UI: <http://localhost:8080/api/docs>** (see
[How to view the Swagger UI](#-how-to-view-the-swagger-ui)). Check which brain is playing with
`curl localhost:8000/api/health` (`opponent_agent` is `claude_code`, `claude` or `heuristic`).

## 📖 How to view the Swagger UI

The API is self-documenting. FastAPI builds an OpenAPI 3 schema from the pydantic models and
route definitions and serves it as an interactive **Swagger UI** page.

**Step by step**

1. Start the app (`docker compose up --build`, or `uvicorn app.main:app --reload` in dev mode).
2. Open your browser at **<http://localhost:8080/api/docs>**.
   * Via Docker this goes through the nginx frontend. <http://localhost:8000/api/docs> hits the
     FastAPI container directly and shows the same page.
   * In dev mode (uvicorn only) use <http://localhost:8000/api/docs>.
3. Endpoints are grouped by tag: **pokemon**, **trainers**, **battles**, **meta**. Click one to
   expand it and see its parameters, request body schema, example payloads and response models.
4. Press **Try it out**, edit the pre-filled example (for instance set `"format": "double"` on
   `POST /api/battles`), then **Execute**. The live response, status code and an equivalent
   `curl` command appear below. You can play a whole battle from this page: copy the `id` from
   the create response into `POST /api/battles/{battle_id}/turn`.
5. Scroll to the bottom for the **Schemas** section, which lists every pydantic model
   (`CreateBattleRequest`, `TurnRequest`, `BattleOut`, …) with field types and descriptions.

**All documentation URLs**

| URL | What |
|---|---|
| <http://localhost:8080/api/docs> | **Swagger UI** – interactive, try every endpoint in the browser |
| <http://localhost:8080/api/redoc> | ReDoc – the same schema as a readable reference page |
| <http://localhost:8080/api/openapi.json> | Raw OpenAPI 3 JSON, importable into Postman or Insomnia |

Replace `8080` with `8000` to bypass nginx. The paths are configured in
[`backend/app/main.py`](backend/app/main.py) (`docs_url`, `redoc_url`, `openapi_url`).

## Claude login inside Docker

The compose file bind-mounts `~/.claude` and `~/.claude.json` into the backend container so
the bundled Claude Code CLI can use your existing `claude login`. If you have never logged in
on this machine, run `claude login` once on the host first (or drop the two volume lines to
run with the heuristic trainer).

> **WSL tip:** if `docker compose` says *permission denied* on `/var/run/docker.sock`, your
> user was just added to the `docker` group. Close and reopen the terminal (or run
> `wsl --shutdown` from PowerShell) and try again. Until then you can drive Docker Desktop
> through its Windows CLI with `make up-win`, which forwards the mount paths correctly.

## Local development

```bash
# backend (Python 3.12+, uses uv)
cd backend
uv run --extra dev pytest -q          # tests
uv run uvicorn app.main:app --reload  # http://localhost:8000

# frontend (Node 20+)
cd frontend
npm install
npm run dev                            # http://localhost:5173, proxies /api → :8000
```

Or use the Makefile: `make test`, `make lint`, `make backend`, `make frontend`, `make up`.

## Opponent agent options

| `OPPONENT_AGENT` | Needs | How it works |
|---|---|---|
| `claude_code` | Claude Code CLI installed and logged in (`claude login`) | Runs `claude -p … --json-schema` per decision with extended thinking off (`MAX_THINKING_TOKENS=0`; the briefing already has the numbers). Uses your Claude subscription, no API credits. ~10 s per turn with Haiku. |
| `claude` | `ANTHROPIC_API_KEY` with credits | Anthropic Messages API with structured outputs and prompt caching (effort and refusal fallbacks are added on models that support them). Haiku 4.5 by default: about a tenth of a cent per decision. ~2–4 s per turn. |
| `heuristic` | nothing | Rule-based: expected damage, KO checks, switching on bad matchups. Instant. |
| `auto` (default) | – | `claude` if a key is set, else `claude_code` if the CLI is found, else `heuristic`. |

All LLM paths validate the returned action against the real battle state and fall back to
the heuristic on timeouts, CLI/API errors, refusals or invalid choices, so a battle never stalls.
The Claude Code path is meant for personal/local use on a machine where you are logged in.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `OPPONENT_AGENT` | `auto` | See table above. |
| `ANTHROPIC_API_KEY` | – | Required only for `OPPONENT_AGENT=claude`. |
| `OPPONENT_MODEL` | `claude-haiku-4-5` | The one model used for every LLM call (trainer and coach, API and CLI paths). Haiku is the cheapest (~$1/$5 per MTok); `claude-sonnet-5` and `claude-opus-5` play better at 2x / 5x the cost. |
| `OPPONENT_EFFORT` | `low` | API path, Opus/Sonnet 5 only (ignored on Haiku): `low` / `medium` / `high`. |
| `OPPONENT_TIMEOUT_SECONDS` | `90` | Per-decision timeout before the heuristic takes over. |
| `CLAUDE_CODE_BIN` | `claude` | Path to the Claude Code CLI binary. |
| `POKEMON_CSV_PATH` | `backend/data/pokemon.csv` | Dataset location. |
| `CORS_ORIGINS` | dev + nginx origins | Comma-separated allowed origins. |
| `BATTLE_LEVEL` / `MAX_TEAM_SIZE` | `50` / `4` | Battle tuning. |

## API

Every endpoint below can be explored and executed interactively in the Swagger UI at
<http://localhost:8080/api/docs>.

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Status, dataset size, active agent |
| GET | `/api/pokemon?q=&type=&generation=&include_legendary=&limit=&offset=` | Search Pokémon |
| GET | `/api/pokemon/{dex}` | Full details, weaknesses, generated moves |
| GET | `/api/types` | Type list with UI colours |
| GET | `/api/trainers` | Opponent roster |
| POST | `/api/battles` | `{ "team": [6, 25], "trainer_id": "misty", "format": "single" }` → battle state (`format: "double"` for 2v2) |
| GET | `/api/battles/{id}` | Current state |
| POST | `/api/battles/{id}/turn` | Singles: `{ "action": {"kind":"move","move_index":0} }`. Doubles: `{ "actions": [{"kind":"move","position":0,"move_index":1,"target_position":1}, {"kind":"switch","position":1,"slot":2}] }`. Bag: `{"kind":"item","item":"potion"}` |
| POST | `/api/battles/{id}/advice` | `{ "position": 0 }` → the coach's recommended `action` (submittable as-is), summary and reasoning |

Every battle response includes the `events` produced by that request (each damage/heal/faint
event names its `target_side` / `target_slot` / `target_position`, which the UI uses to
animate HP bars) and `opponent_decisions`: one entry per opponent Pokémon that acted, with its
taunt, reasoning and which agent produced it. Opponent movesets are hidden from the client.
When `phase` is `player_must_switch`, `positions_to_replace` lists the positions that need a
switch action.

### Double battles

* Each side has two field positions (0 and 1); `player_active` / `opponent_active` map a
  position to a team slot (`-1` = empty).
* You submit one action per living position. Damaging moves take a `target_position`; if that
  foe has already fainted the move is redirected to the other one.
* The service calls the opponent agent once **per active opponent Pokémon**, concurrently
  (`asyncio.gather`), each with a briefing written from that Pokémon's point of view that
  lists its partner and both foes with per-target expected damage.
* Fainted Pokémon are replaced from the bench at the end of the turn. If the bench is empty
  the position stays empty and the battle continues 2v1 / 1v1.

### How to see which endpoints are being called

* **In the UI:** the *API activity* panel in the battle sidebar logs every request the browser
  makes (method, path, HTTP status, latency) and counts them.
* **In the browser:** DevTools → Network tab, filter by `api`.
* **On the server:** `docker compose logs -f backend` shows uvicorn's access log, one line per
  request, plus the agent's decisions and any fallbacks.
* **Swagger:** each endpoint's *Execute* button shows the exact `curl` it ran.

## Where pydantic is used

| File | Role |
|---|---|
| [`backend/app/schemas.py`](backend/app/schemas.py) | Every request and response model (`CreateBattleRequest`, `TurnRequest` with a discriminated union of actions and a cross-field validator, `BattleOut`, …). FastAPI validates input against these and builds the Swagger schema from them. |
| [`backend/app/config.py`](backend/app/config.py) | `pydantic-settings` `BaseSettings` – typed environment configuration loaded from `.env`. |
| [`backend/app/agents/decision.py`](backend/app/agents/decision.py) | `TrainerDecision` – the JSON object the LLM must return; validated with `model_validate` before an action is accepted. |

## Project layout

```
backend/
  app/
    main.py            FastAPI app factory, lifespan wiring, CORS
    config.py          pydantic-settings
    schemas.py         API models
    api/               routers: pokemon, trainers, battles
    data/              CSV loader + in-memory repository
    domain/            types, moves, trainers, battle engine (singles + doubles; pure, no I/O)
    agents/            OpponentAgent protocol, briefing builder, shared decision schema,
                       LLM base class, Claude API agent, Claude Code CLI agent, heuristic agent
    services/          BattleService: sessions, locking, agent orchestration
  data/pokemon.csv     the Kaggle dataset
  tests/               pytest suite (engine, moves, agents incl. fake-CLI tests, API)
frontend/
  src/
    App.tsx            screen flow: team → trainer → battle → result
    hooks/useBattle.ts battle state + event replay animation
    components/        TeamSelect, TrainerSelect, BattleScreen, HpBar, ResultScreen…
    api/client.ts      typed fetch wrapper
docker-compose.yml     backend + nginx-served frontend
```

## Data & assets

* Dataset: Rounak Banik, *The Complete Pokémon Dataset* (Kaggle, CC0). Bundled as
  `backend/data/pokemon.csv`; replace it with a fresh download if you like.
* Pokémon artwork and animated sprites are hot-linked from the
  [PokeAPI/sprites](https://github.com/PokeAPI/sprites) repository; trainer portraits from
  Pokémon Showdown. Pokémon is © Nintendo / Creatures Inc. / GAME FREAK. This is a fan project.

## Notes & limitations

* Battles are kept in process memory (last 500). Restarting the backend clears them.
* No persistence or accounts.
* Weather, abilities, items and non-volatile status conditions are not simulated.
