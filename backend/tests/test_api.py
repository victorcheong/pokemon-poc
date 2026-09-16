def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["pokemon_loaded"] == 801
    assert body["opponent_agent"] == "heuristic" and body["model"] is None


def test_list_and_detail(client):
    r = client.get("/api/pokemon", params={"q": "char", "limit": 5})
    assert r.status_code == 200
    items = r.json()["items"]
    assert items and items[0]["sprites"]["artwork"].endswith("/4.png")

    r = client.get("/api/pokemon/6")
    assert r.status_code == 200
    detail = r.json()
    assert detail["name"] == "Charizard"
    assert len(detail["moves"]) == 4
    assert "rock" in detail["weaknesses"]

    assert client.get("/api/pokemon/9999").status_code == 404


def test_trainers_and_types(client):
    trainers = client.get("/api/trainers").json()
    assert any(t["id"] == "cynthia" for t in trainers)
    assert len(client.get("/api/types").json()) == 18


def test_full_battle_flow(client):
    r = client.post("/api/battles", json={"team": [150, 6], "trainer_id": "brock"})
    assert r.status_code == 201, r.text
    battle = r.json()
    assert battle["phase"] == "choose_action"
    assert battle["format"] == "single" and battle["player_active"] == [0]
    assert len(battle["opponent_team"]) == 2
    assert battle["opponent_team"][0]["moves"] == []  # hidden
    assert battle["trainer"]["name"] == "Brock"
    bid = battle["id"]

    for _ in range(60):
        battle = client.get(f"/api/battles/{bid}").json()
        if battle["phase"] == "finished":
            break
        if battle["phase"] == "player_must_switch":
            slot = next(p["slot"] for p in battle["player_team"] if not p["fainted"])
            action = {"kind": "switch", "slot": slot}
        else:
            active = battle["player_team"][battle["player_active"][0]]
            idx = next(i for i, m in enumerate(active["moves"]) if m["pp"] > 0)
            action = {"kind": "move", "move_index": idx}
        r = client.post(f"/api/battles/{bid}/turn", json={"action": action})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["events"]
        if action["kind"] == "move":
            assert body["opponent_decisions"] and body["opponent_decisions"][0]["taunt"]
    assert battle["phase"] == "finished"
    assert battle["winner"] in {"player", "opponent"}

    r = client.post(f"/api/battles/{bid}/turn", json={"action": {"kind": "move", "move_index": 0}})
    assert r.status_code == 409


def test_double_battle_flow(client):
    r = client.post(
        "/api/battles", json={"team": [150, 6, 9, 3], "trainer_id": "cynthia", "format": "double"}
    )
    assert r.status_code == 201, r.text
    battle = r.json()
    bid = battle["id"]
    assert battle["format"] == "double"
    assert battle["player_active"] == [0, 1] and battle["opponent_active"] == [0, 1]
    assert len(battle["opponent_team"]) == 4

    for _ in range(80):
        if battle["phase"] == "finished":
            break
        if battle["phase"] == "player_must_switch":
            on_field = set(battle["player_active"])
            bench = [
                p["slot"]
                for p in battle["player_team"]
                if not p["fainted"] and p["slot"] not in on_field
            ]
            actions = [
                {"kind": "switch", "position": pos, "slot": slot}
                for pos, slot in zip(battle["positions_to_replace"], bench, strict=False)
            ]
        else:
            living_foes = [
                pos
                for pos, slot in enumerate(battle["opponent_active"])
                if slot >= 0 and not battle["opponent_team"][slot]["fainted"]
            ]
            actions = []
            for pos, slot in enumerate(battle["player_active"]):
                if slot < 0 or battle["player_team"][slot]["fainted"]:
                    continue
                mv = battle["player_team"][slot]["moves"]
                idx = next(i for i, m in enumerate(mv) if m["pp"] > 0)
                actions.append(
                    {
                        "kind": "move",
                        "position": pos,
                        "move_index": idx,
                        "target_position": living_foes[0],
                    }
                )
        r = client.post(f"/api/battles/{bid}/turn", json={"actions": actions})
        assert r.status_code == 200, r.text
        battle = r.json()
        if actions[0]["kind"] == "move":
            # One decision per opponent Pokémon that acted.
            acted = [d for d in battle["opponent_decisions"]]
            assert 1 <= len(acted) <= 4
            assert all(d["position"] in (0, 1) for d in acted)
    assert battle["phase"] == "finished"


def test_double_battle_needs_two_pokemon(client):
    r = client.post("/api/battles", json={"team": [6], "format": "double"})
    assert r.status_code == 422


def test_swagger_docs_available(client):
    assert client.get("/api/docs").status_code == 200
    schema = client.get("/api/openapi.json").json()
    assert "/api/battles/{battle_id}/turn" in schema["paths"]
    assert schema["info"]["title"] == "Pokémon Battle API"


def test_validation_errors(client):
    assert client.post("/api/battles", json={"team": []}).status_code == 422
    assert client.post("/api/battles", json={"team": [1, 1]}).status_code == 422
    assert client.post("/api/battles", json={"team": [1, 2, 3, 4, 5]}).status_code == 422
    assert client.post("/api/battles", json={"team": [99999]}).status_code == 422
    assert (
        client.post("/api/battles", json={"team": [1], "trainer_id": "nobody"}).status_code == 422
    )
    assert client.get("/api/battles/nope").status_code == 404


def test_bag_item_heals_and_is_consumed(client):
    r = client.post("/api/battles", json={"team": [143], "trainer_id": "brock"})
    battle = r.json()
    bid = battle["id"]
    assert {i["id"]: i["count"] for i in battle["player_items"]} == {
        "potion": 2,
        "hyper_potion": 1,
        "full_restore": 1,
    }
    # Full HP: item is refused.
    r = client.post(f"/api/battles/{bid}/turn", json={"action": {"kind": "item", "item": "potion"}})
    assert r.status_code == 409 and "already full" in r.json()["detail"]
    # Take a hit, then heal.
    for _ in range(6):
        battle = client.post(
            f"/api/battles/{bid}/turn", json={"action": {"kind": "move", "move_index": 3}}
        ).json()
        me = battle["player_team"][0]
        if me["current_hp"] < me["max_hp"] - 30 and battle["phase"] == "choose_action":
            break
    hp_before = battle["player_team"][0]["current_hp"]
    battle = client.post(
        f"/api/battles/{bid}/turn", json={"action": {"kind": "item", "item": "potion"}}
    ).json()
    heal_events = [e for e in battle["events"] if e["type"] == "item"]
    assert heal_events and "Potion" in heal_events[0]["text"]
    assert next(i["count"] for i in battle["player_items"] if i["id"] == "potion") == 1
    healed = next(e for e in battle["events"] if e["type"] == "heal" and e["side"] == "player")
    assert healed["hp_after"] > hp_before


def test_advice_endpoint_returns_submittable_action(client):
    r = client.post("/api/battles", json={"team": [6, 25], "trainer_id": "misty"})
    bid = r.json()["id"]
    r = client.post(f"/api/battles/{bid}/advice", json={"position": 0})
    assert r.status_code == 200, r.text
    advice = r.json()
    assert advice["pokemon"] == "Charizard"
    assert advice["source"] == "heuristic"
    assert advice["action"]["kind"] in {"move", "switch", "item"}
    assert advice["summary"] and advice["reasoning"]
    # The recommended action is accepted by the turn endpoint as-is.
    r = client.post(f"/api/battles/{bid}/turn", json={"action": advice["action"]})
    assert r.status_code == 200, r.text
    assert client.post(f"/api/battles/{bid}/advice", json={"position": 1}).status_code == 409
    assert client.post("/api/battles/nope/advice", json={"position": 0}).status_code == 404
