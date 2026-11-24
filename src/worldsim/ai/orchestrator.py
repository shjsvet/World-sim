"""Оркестратор ИИ-года: решения правителей, шаг движка и мысли."""

from __future__ import annotations

from worldsim.ai.client import LLMClient
from worldsim.ai.diplomacy_chat import DiplomacyChat
from worldsim.ai.ruler import LLMRuler, RulerDecision, fallback_decision
from worldsim.core.faction import Faction
from worldsim.core.rulers import DiplomaticMessage, RulerThought
from worldsim.core.state import WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules import AICommand


class AIRulerOrchestrator:
    """Проводит один год с решениями ИИ-правителей.

    Без клиента используется детерминированный fallback: сеть не нужна,
    симуляция остаётся воспроизводимой.
    """

    def __init__(
        self,
        client: LLMClient | None = None,
        *,
        auto_chat: bool = False,
    ) -> None:
        self._client = client
        self._ruler = LLMRuler(client) if client is not None else None
        self._auto_chat_enabled = auto_chat

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
        messages = self._auto_chat(engine.state) if self._auto_chat_enabled else ()
        engine.step()
        if thoughts:
            engine.record_thoughts(tuple(thoughts))
        if messages:
            engine.record_messages(messages)
        return engine.state

    def _auto_chat(self, state: WorldState) -> tuple[DiplomaticMessage, ...]:
        """Раз в три года открывает канал между двумя фракциями."""
        if len(state.factions) < 2 or state.year % 3 != 0:
            return ()
        if any(message.year == state.year for message in state.diplomatic_messages):
            return ()
        pair = _dialogue_pair(state)
        if pair is None:
            return ()
        sender, recipient, topic = pair
        return DiplomacyChat(self._client).open_channel(sender, recipient, topic, state)

    def open_channel(
        self,
        engine: SimulationEngine,
        sender_id: int,
        recipient_id: int,
        topic: str = "peace",
    ) -> tuple[DiplomaticMessage, ...]:
        """Открывает канал между двумя фракциями и сохраняет сообщение."""
        state = engine.state
        factions = {faction.id: faction for faction in state.factions}
        try:
            sender = factions[sender_id]
            recipient = factions[recipient_id]
        except KeyError as exc:
            raise ValueError("фракция отсутствует в снимке") from exc
        messages = DiplomacyChat(self._client).open_channel(sender, recipient, topic, state)
        engine.record_messages(messages)
        return messages

    def _decide(self, state: WorldState, faction: Faction) -> RulerDecision:
        """Выбирает LLM или fallback для фракции."""
        if self._ruler is not None:
            return self._ruler.decide(state, faction)
        return fallback_decision(state, faction)


def _dialogue_pair(
    state: WorldState,
) -> tuple[Faction, Faction, str] | None:
    """Выбирает пару для автоматической переписки и тему."""
    factions = sorted(state.factions, key=lambda faction: faction.id)
    for war in state.wars:
        if not war.active:
            continue
        first = next((item for item in factions if item.id == war.attacker_id), None)
        second = next((item for item in factions if item.id == war.defender_id), None)
        if first is not None and second is not None:
            return first, second, "peace"
    for first in factions:
        for second in factions:
            if first.id == second.id:
                continue
            if first.food_stockpile > second.food_stockpile + 40:
                return first, second, "trade"
    if len(factions) >= 2:
        return factions[0], factions[1], "offer"
    return None
