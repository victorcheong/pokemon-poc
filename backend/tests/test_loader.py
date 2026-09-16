from app.domain.types import PokemonType


def test_dataset_loads_all_rows(repo):
    assert len(repo) == 801


def test_pikachu_row_parsed(repo):
    pika = repo.get(25)
    assert pika is not None
    assert pika.name == "Pikachu"
    assert pika.type1 is PokemonType.ELECTRIC
    assert pika.type2 is None
    assert pika.effectiveness_against(PokemonType.GROUND) == 2.0
    assert pika.effectiveness_against(PokemonType.FLYING) == 0.5
    assert "Static" in pika.abilities


def test_fighting_column_alias(repo):
    # Rock/Ground Geodude is weak to Fighting; dataset column is `against_fight`.
    geodude = repo.get(74)
    assert geodude.effectiveness_against(PokemonType.FIGHTING) == 2.0


def test_search_filters(repo):
    fire_gen1 = repo.search(type_=PokemonType.FIRE, generation=1)
    assert all(PokemonType.FIRE in r.types and r.generation == 1 for r in fire_gen1)
    assert any(r.name == "Charizard" for r in fire_gen1)
    assert repo.search(query="mew") and all(
        "mew" in r.name.lower() for r in repo.search(query="mew")
    )
