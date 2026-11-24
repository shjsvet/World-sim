"""UI-обёртки ИИ-функций без Streamlit."""

from __future__ import annotations

from pathlib import Path

from worldsim.ai.chronicler import ChronicleWriter, save_chapter
from worldsim.ai.client import AIUnavailableError, LLMClient, create_client
from worldsim.ai.world_builder import WorldBlueprint, apply_config, apply_offline_config
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.generator.world import create_world


def manual_config(
    *,
    seed: int = 42,
    size: int = 32,
    initial_factions: int = 2,
    aggression: float = 0.5,
    growth_rate: float = 0.02,
    plague_chance: float = 0.01,
    magic_level: float = 0.0,
) -> WorldConfig:
    """Собирает конфигурацию из полей ручной формы."""
    return WorldConfig(
        seed=seed,
        size=size,
        initial_factions=initial_factions,
        aggression=aggression,
        growth_rate=growth_rate,
        plague_chance=plague_chance,
        magic_level=magic_level,
    )


def safe_client(provider: str | None = None) -> tuple[LLMClient | None, str | None]:
    """Создаёт клиента и возвращает понятную ошибку вместо исключения."""
    try:
        return create_client(provider), None
    except AIUnavailableError as exc:
        return None, str(exc)


def create_ai_world(
    description: str,
    client: LLMClient,
    *,
    root: Path | None = None,
) -> tuple[WorldState, WorldBlueprint, Path]:
    """Создаёт мир по описанию через ИИ."""
    return apply_config(description, client, root=root)


def create_offline_world(
    description: str,
    base_config: WorldConfig,
    *,
    root: Path | None = None,
) -> tuple[WorldState, WorldBlueprint, Path]:
    """Создаёт мир по описанию без ИИ, разбирая культуры из текста."""
    return apply_offline_config(description, base_config, root=root)


def manual_world(
    *,
    seed: int = 42,
    size: int = 32,
    initial_factions: int = 2,
    aggression: float = 0.5,
    growth_rate: float = 0.02,
    plague_chance: float = 0.01,
    magic_level: float = 0.0,
) -> WorldState:
    """Создаёт мир по ручным параметрам."""
    return create_world(
        manual_config(
            seed=seed,
            size=size,
            initial_factions=initial_factions,
            aggression=aggression,
            growth_rate=growth_rate,
            plague_chance=plague_chance,
            magic_level=magic_level,
        )
    )


def write_chapter_for_engine(
    engine: SimulationEngine,
    client: LLMClient,
    year_from: int,
    year_to: int,
    *,
    directory: Path,
    seed: int | None = None,
) -> Path:
    """Пишет главу летописи за период и сохраняет её в каталог."""
    events = engine.chronicle.between(year_from, year_to)
    writer = ChronicleWriter(client)
    text = writer.write_chapter(events, year_from, year_to)
    return save_chapter(
        directory,
        text,
        year_from=year_from,
        year_to=year_to,
        seed=seed,
        model=writer.model,
    )
