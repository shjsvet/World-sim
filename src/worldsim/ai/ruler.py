"""Принятие решений ИИ-правителем фракции."""

from __future__ import annotations

import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from worldsim.ai.client import AIUnavailableError, LLMClient, Message
from worldsim.core.faction import Faction
from worldsim.core.geography import ResourceType
from worldsim.core.state import WorldState


class RulerAction(StrEnum):
    """Действия, доступные ИИ-правителю."""

    BUILD_ACADEMY = "build_academy"
    RECRUIT = "recruit"
    EXTRACT_RESOURCE = "extract_resource"
    REDISTRIBUTE_POPULATION = "redistribute_population"
    PROPOSE_PEACE = "propose_peace"
    OFFER_TRADE = "offer_trade"
    MOVE_ARMY = "move_army"
    FOUND_RELIGION = "found_religion"
    HOLD = "hold"


class RulerDecision(BaseModel):
    """Решение правителя: действие, параметры и мысль."""

    model_config = ConfigDict(frozen=True)

    action: RulerAction
    target_tile_id: int | None = Field(default=None, ge=0)
    amount: int = Field(default=0, ge=0)
    message: str = Field(default="", max_length=500)
    thought: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(default=0.5, ge=0, le=1)


SYSTEM_PROMPT = (
    "Ты — ИИ-правитель фракции в симуляции мира. Реши, что делать в этом году, "
    "и верни строго один JSON-объект без пояснений и markdown. Поля: "
    '"action" (одно из: '
    + ", ".join(action.value for action in RulerAction)
    + '), "target_tile_id" (целое или null), "amount" (целое >= 0), '
    '"message" (строка), "thought" (1–1000 символов, объяснение решения), '
    '"confidence" (0..1). Действуй только в интересах своей фракции и не '
    "выдумывай факты, которых нет в переданных данных."
)


class LLMRuler:
    """Принимает решения через LLM и падает в детерминированный fallback."""

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def decide(self, state: WorldState, faction: Faction) -> RulerDecision:
        """Возвращает решение правителя или fallback без сети."""
        messages = [
            Message(role="system", content=SYSTEM_PROMPT),
            Message(
                role="user",
                content=json.dumps(
                    _faction_context(state, faction),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            ),
        ]
        try:
            answer = self._client.complete(messages, json_mode=True)
        except AIUnavailableError:
            return fallback_decision(state, faction)
        try:
            payload = json.loads(answer)
            if not isinstance(payload, dict):
                raise ValueError("ожидался JSON-объект")
            decision = RulerDecision.model_validate(payload)
            if decision.target_tile_id is not None and (
                decision.target_tile_id >= len(state.map.tiles)
            ):
                raise ValueError("цель вне карты")
            return decision
        except (json.JSONDecodeError, ValueError):
            return fallback_decision(state, faction)


def fallback_decision(state: WorldState, faction: Faction) -> RulerDecision:
    """Детерминированное решение без ИИ."""
    owned = [tile for tile in state.map.tiles if tile.owner_id == faction.id]
    if not owned:
        return RulerDecision(
            action=RulerAction.HOLD,
            thought="У фракции нет территорий — жду развития событий.",
            confidence=0.2,
        )

    if faction.food_stockpile <= 0:
        resource_tiles = sorted(
            (
                tile
                for tile in owned
                if tile.resource_type is not ResourceType.NONE and tile.resource_depletion > 0
            ),
            key=lambda tile: (
                tile.resource_type is not ResourceType.FOOD,
                -tile.resource_depletion,
                tile.id,
            ),
        )
        if resource_tiles:
            target = resource_tiles[0]
            return RulerDecision(
                action=RulerAction.EXTRACT_RESOURCE,
                target_tile_id=target.id,
                amount=max(1, min(20, int(target.resource_depletion))),
                thought=(
                    f"Запасы еды закончились — нужно срочно добыть ресурсы на тайле {target.id}."
                ),
                confidence=0.8,
            )
        if faction.treasury >= 2.0:
            amount = max(1, min(10, int(faction.treasury // 2)))
            return RulerDecision(
                action=RulerAction.RECRUIT,
                amount=amount,
                thought="Еды нет, но есть золото — наберу армию для защиты.",
                confidence=0.6,
            )

    if faction.morale < 0.3:
        return RulerDecision(
            action=RulerAction.PROPOSE_PEACE,
            thought="Люди устали от войны, пора предложить мир.",
            confidence=0.7,
        )

    return RulerDecision(
        action=RulerAction.HOLD,
        thought="Сейчас нет срочных угроз — продолжаю накапливать силы.",
        confidence=0.4,
    )


def _faction_context(state: WorldState, faction: Faction) -> dict[str, object]:
    """Собирает компактную сводку для промпта."""
    owned = [tile for tile in state.map.tiles if tile.owner_id == faction.id]
    population = sum(tile.population for tile in owned)
    best_tiles = sorted(
        owned,
        key=lambda tile: (-tile.mana_density, -tile.fertility, tile.id),
    )[:5]
    wars = [
        {
            "with": (war.defender_id if war.attacker_id == faction.id else war.attacker_id),
            "active": war.active,
            "truce_until": war.truce_until_year,
        }
        for war in state.wars
        if faction.id in {war.attacker_id, war.defender_id}
    ]
    return {
        "year": state.year,
        "faction": {
            "id": faction.id,
            "name": faction.name,
            "culture": faction.culture,
            "treasury": faction.treasury,
            "food_stockpile": faction.food_stockpile,
            "army_size": faction.army_size,
            "morale": faction.morale,
            "mana_pool": faction.mana_pool,
            "magic_affinity": faction.magic_affinity,
            "tech_level": faction.tech_level,
            "resources": faction.resources,
            "aggressiveness": faction.aggressiveness,
        },
        "territory": {
            "tiles": len(owned),
            "population": population,
            "cities": sum(1 for tile in owned if tile.is_city),
            "mana_tiles": sum(1 for tile in owned if tile.mana_density >= 50),
            "best_tiles": [
                {
                    "id": tile.id,
                    "population": tile.population,
                    "fertility": tile.fertility,
                    "mana_density": tile.mana_density,
                    "resource": tile.resource_type.value,
                }
                for tile in best_tiles
            ],
        },
        "wars": wars,
        "allowed_actions": [action.value for action in RulerAction],
    }
