"""Оркестратор ИИ-года: решения правителей, шаг движка и мысли."""

from __future__ import annotations

from worldsim.ai.client import LLMClient
from worldsim.ai.ruler import LLMRuler, RulerDecision, fallback_decision
from worldsim.core.faction import Faction
from worldsim.core.rulers import RulerThought
from worldsim.core.state import WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules import AICommand


class AIRulerOrchestrator:
    """Проводит один год с решениями ИИ-правителей.

    Без клиента используется детерминированный fallback: сеть не нужна,
    симуляция остаётся воспроизводимой.
    """

    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client
        self._ruler = LLMRuler(client) if client is not None else None

    def run_year(self, engine: SimulationEngine) -> WorldState:
        """Принимает решения, выполняет шаг и записывает мысли правителей."""
        state = engine.state
        profiles = {profile.faction_id: profile for profile in state.rulers}
        commands: list[AICommand] = []
        thoughts: list[RulerThought] = []
        next_thought_id = max((thought.id for thought in state.thoughts), default=-1) + 1

        for faction in state.factions:
            profile = profiles.get(faction.id)
            if profile is None:
                continue
            if state.year % profile.decision_interval != 0:
                continue
            decision = self._decide(state, faction)
            commands.append(AICommand(faction_id=faction.id, decision=decision))
            thoughts.append(
                RulerThought(
                    id=next_thought_id,
                    faction_id=faction.id,
                    year=state.year,
                    text=decision.thought,
                    action=decision.action.value,
                    target_tile_id=decision.target_tile_id,
                )
            )
            next_thought_id += 1

        engine.queue_decisions(commands)
        engine.step()
        if thoughts:
            engine.record_thoughts(tuple(thoughts))
        return engine.state

    def _decide(self, state: WorldState, faction: Faction) -> RulerDecision:
        """Выбирает LLM или fallback для фракции."""
        if self._ruler is not None:
            return self._ruler.decide(state, faction)
        return fallback_decision(state, faction)
