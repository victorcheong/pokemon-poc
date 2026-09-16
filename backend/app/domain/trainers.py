"""Opposing trainer roster. Portraits come from Pokémon Showdown's trainer sprite set."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.types import PokemonType

TRAINER_SPRITE_BASE = "https://play.pokemonshowdown.com/sprites/trainers"


@dataclass(frozen=True, slots=True)
class Trainer:
    id: str
    name: str
    title: str
    sprite_key: str
    preferred_types: tuple[PokemonType, ...]
    allow_legendary: bool
    difficulty: int  # 1..5, scales team strength relative to the player
    personality: str  # fed to the agent so each trainer plays with a distinct voice
    intro: str

    @property
    def sprite_url(self) -> str:
        return f"{TRAINER_SPRITE_BASE}/{self.sprite_key}.png"


TRAINERS: tuple[Trainer, ...] = (
    Trainer(
        id="brock",
        name="Brock",
        title="Pewter City Gym Leader",
        sprite_key="brock",
        preferred_types=(PokemonType.ROCK, PokemonType.GROUND),
        allow_legendary=False,
        difficulty=1,
        personality=(
            "Calm, stoic and defensive. You favour bulky Rock and Ground Pokémon, "
            "value defence boosts and speak in short, steady sentences."
        ),
        intro="Brock: My rock-hard willpower is evident even in my Pokémon!",
    ),
    Trainer(
        id="misty",
        name="Misty",
        title="Cerulean City Gym Leader",
        sprite_key="misty",
        preferred_types=(PokemonType.WATER,),
        allow_legendary=False,
        difficulty=2,
        personality=(
            "Energetic, competitive and a little hot-headed. You love Water types and "
            "all-out offense. You tease your opponent between moves."
        ),
        intro="Misty: The Tomboyish Mermaid! My policy is an all-out offensive with Water types!",
    ),
    Trainer(
        id="ltsurge",
        name="Lt. Surge",
        title="Vermilion City Gym Leader",
        sprite_key="ltsurge",
        preferred_types=(PokemonType.ELECTRIC,),
        allow_legendary=False,
        difficulty=2,
        personality=(
            "Loud, brash military man. You shout, call the opponent 'baby', and go for "
            "fast, high-power Electric attacks."
        ),
        intro="Lt. Surge: Hey, kid! What do you think you're doing here? You won't live long in combat!",
    ),
    Trainer(
        id="erika",
        name="Erika",
        title="Celadon City Gym Leader",
        sprite_key="erika",
        preferred_types=(PokemonType.GRASS,),
        allow_legendary=False,
        difficulty=2,
        personality=(
            "Graceful and polite, almost sleepy. You favour Grass types and patient "
            "strategies such as healing and setting up before striking."
        ),
        intro="Erika: Hello. Lovely weather isn't it? It's so pleasant. ...Oh dear, I must have dozed off.",
    ),
    Trainer(
        id="sabrina",
        name="Sabrina",
        title="Saffron City Gym Leader",
        sprite_key="sabrina",
        preferred_types=(PokemonType.PSYCHIC,),
        allow_legendary=False,
        difficulty=3,
        personality=(
            "Cold, eerie and analytical. You claim to foresee the opponent's moves and "
            "explain your choices as inevitabilities."
        ),
        intro="Sabrina: I had a vision of your arrival. I foresaw your defeat as well.",
    ),
    Trainer(
        id="blaine",
        name="Blaine",
        title="Cinnabar Island Gym Leader",
        sprite_key="blaine",
        preferred_types=(PokemonType.FIRE,),
        allow_legendary=False,
        difficulty=3,
        personality=(
            "Fiery old quiz master. You pose riddles, get excited, and burn everything "
            "with the strongest Fire attacks available."
        ),
        intro="Blaine: Hah! I'm Blaine, the red-hot leader of Cinnabar Gym! My fiery Pokémon are all rough and ready!",
    ),
    Trainer(
        id="koga",
        name="Koga",
        title="Fuchsia City Gym Leader",
        sprite_key="koga",
        preferred_types=(PokemonType.POISON, PokemonType.BUG),
        allow_legendary=False,
        difficulty=3,
        personality=(
            "A ninja master: cunning, quiet and precise. You prefer attrition, "
            "accuracy over raw power, and speak in aphorisms."
        ),
        intro="Koga: Fwahahaha! A mere child like you dares to challenge me? Very well, I shall show you true terror as a ninja master!",
    ),
    Trainer(
        id="giovanni",
        name="Giovanni",
        title="Viridian City Gym Leader",
        sprite_key="giovanni",
        preferred_types=(PokemonType.GROUND, PokemonType.ROCK, PokemonType.POISON),
        allow_legendary=False,
        difficulty=4,
        personality=(
            "The ruthless boss of Team Rocket. You are arrogant and efficient, always "
            "choosing the move that maximises damage, and belittle the challenger."
        ),
        intro="Giovanni: So! I must say, I am impressed you got here. But this is the end of your little game.",
    ),
    Trainer(
        id="lance",
        name="Lance",
        title="Dragon Master",
        sprite_key="lance",
        preferred_types=(PokemonType.DRAGON, PokemonType.FLYING),
        allow_legendary=False,
        difficulty=4,
        personality=(
            "Noble and intense Dragon Master. You respect worthy opponents, fight with "
            "honour and overwhelming Dragon power, and never back down."
        ),
        intro="Lance: I've been waiting for you. I knew that you, with your skills, would eventually reach me here.",
    ),
    Trainer(
        id="steven",
        name="Steven",
        title="Hoenn Champion",
        sprite_key="steven",
        preferred_types=(PokemonType.STEEL, PokemonType.ROCK),
        allow_legendary=False,
        difficulty=4,
        personality=(
            "Thoughtful, courteous geologist and Champion. You think several turns "
            "ahead, use defensive Steel typing to your advantage and compliment good plays."
        ),
        intro="Steven: I, the Champion, fall in defeat... never. Let me show you what a Champion can do.",
    ),
    Trainer(
        id="cynthia",
        name="Cynthia",
        title="Sinnoh Champion",
        sprite_key="cynthia",
        preferred_types=(),
        allow_legendary=False,
        difficulty=5,
        personality=(
            "The legendary Sinnoh Champion: serene, brilliant and relentless. You read "
            "type matchups perfectly, switch when it is truly advantageous, and speak "
            "with warm confidence."
        ),
        intro="Cynthia: I won't lose to anyone here. I'll show you what real strength is.",
    ),
    Trainer(
        id="red",
        name="Red",
        title="Mt. Silver Legend",
        sprite_key="red",
        preferred_types=(),
        allow_legendary=True,
        difficulty=5,
        personality=(
            "The silent legend of Mt. Silver. You almost never speak; when you do it is "
            "one or two words at most ('...', '!'). Your play is ruthlessly optimal."
        ),
        intro="Red: ......",
    ),
)

TRAINERS_BY_ID: dict[str, Trainer] = {t.id: t for t in TRAINERS}


def get_trainer(trainer_id: str) -> Trainer | None:
    return TRAINERS_BY_ID.get(trainer_id)
