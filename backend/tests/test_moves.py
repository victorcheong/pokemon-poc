from app.domain.moves import MoveCategory, build_moveset


def test_moveset_has_four_unique_moves(repo):
    for record in repo.all():
        moves = build_moveset(record)
        assert len(moves) == 4, record.name
        assert len({m.name for m in moves}) == 4, record.name
        assert any(m.category is not MoveCategory.STATUS for m in moves)


def test_moveset_is_deterministic(repo):
    charizard = repo.get(6)
    assert [m.name for m in build_moveset(charizard)] == [m.name for m in build_moveset(charizard)]


def test_moveset_uses_stab_and_stat_profile(repo):
    alakazam = repo.get(65)  # special attacker
    names = {m.name for m in build_moveset(alakazam)}
    assert "Psystrike" in names and "Psychic" in names
    machamp = repo.get(68)  # physical attacker
    assert "Close Combat" in {m.name for m in build_moveset(machamp)}
