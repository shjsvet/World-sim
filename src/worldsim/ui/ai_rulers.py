"""UI-хелперы ИИ-правителей без Streamlit."""

from __future__ import annotations

from worldsim.ai.client import LLMClient
from worldsim.ai.orchestrator import AIRulerOrchestrator
from worldsim.core.rulers import DiplomaticMessage, RulerProfile
from worldsim.core.state import WorldState
from worldsim.engine.engine import SimulationEngine


def ensure_rulers(state: WorldState) -> WorldState:
    """Добавляет профили правителей всем фракциям, если их ещё нет."""
    if state.rulers or not state.factions:
        return state
    rulers = tuple(
        RulerProfile(
            faction_id=faction.id,
            name=faction.name,
            decision_interval=1,
        )
        for faction in state.factions
    )
    return state.evolve(rulers=rulers)


def run_ai_year(
    engine: SimulationEngine,
    client: LLMClient | None = None,
) -> WorldState:
    """Проводит один год с ИИ-правителями (LLM или fallback)."""
    return AIRulerOrchestrator(client, auto_chat=True).run_year(engine)


def open_diplomacy(
    engine: SimulationEngine,
    sender_id: int,
    recipient_id: int,
    topic: str = "peace",
    client: LLMClient | None = None,
) -> tuple[DiplomaticMessage, ...]:
    """Открывает канал переписки и сохраняет сообщение."""
    return AIRulerOrchestrator(client).open_channel(
        engine,
        sender_id,
        recipient_id,
        topic,
    )
