"""Принятие решений ИИ-правителем фракции."""

from __future__ import annotations

import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    ISSUE_ORDER = "issue_order"
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
    order_kind: str = Field(default="", max_length=64)
    order_years: int = Field(default=0, ge=0, le=50)
    trade_resource: str = Field(default="food", max_length=32)

    @model_validator(mode="after")
    def _validate_order(self) -> RulerDecision:
        """Приказ должен иметь непустой вид."""
        if self.action is RulerAction.ISSUE_ORDER and not self.order_kind.strip():
            raise ValueError("для ISSUE_ORDER нужен order_kind")
        return self


SYSTEM_PROMPT = (
    "Ты — ИИ-правитель фракции в симуляции мира. Реши, что делать в этом году, "
    "и верни строго один JSON-объект без пояснений и markdown. Поля: "
    '"action" (одно из: '
    + ", ".join(action.value for action in RulerAction)
    + '), "target_tile_id" (целое или null), "amount" (целое >= 0), '
    '"message" (строка), "thought" (1–1000 символов, объяснение решения), '
    '"confidence" (0..1), "order_kind" (для ISSUE_ORDER: accumulate_gold, '
    'recruit или defend), "order_years" (1–50), "trade_resource" '
    "(для OFFER_TRADE: food или ресурс). Действуй только в интересах "
    "своей фракции и не выдумывай факты, которых нет в переданных данных."
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

    trade = _trade_opportunity(state, faction)
    if trade is not None:
        target_tile, amount = trade
        return RulerDecision(
            action=RulerAction.OFFER_TRADE,
            target_tile_id=target_tile,
            amount=amount,
            trade_resource="food",
            thought=("У соседа голод, а у нас избыток еды — предложу обмен на золото."),
            confidence=0.6,
        )

    has_order = any(
        order.faction_id == faction.id and order.years_left > 0 for order in state.standing_orders
    )
    if not has_order:
        return RulerDecision(
            action=RulerAction.ISSUE_ORDER,
            order_kind="accumulate_gold",
            order_years=3,
            thought="Сейчас нет срочных угроз — велю три года копить золото.",
            confidence=0.4,
        )

    return RulerDecision(
        action=RulerAction.HOLD,
        thought="Долгосрочный приказ уже выполняется — продолжаю накапливать силы.",
        confidence=0.4,
    )


def _trade_opportunity(
    state: WorldState,
    faction: Faction,
) -> tuple[int, int] | None:
    """Ищет голодающего соседа с золотом для обмена еды."""
    factions = {item.id: item for item in state.factions}
    if faction.food_stockpile <= 20:
        return None
    for tile in state.map.tiles:
        if tile.owner_id != faction.id:
            continue
        for neighbor in state.map.neighbors(tile.x, tile.y):
            if neighbor.owner_id is None or neighbor.owner_id == faction.id:
                continue
            recipient = factions.get(neighbor.owner_id)
            if recipient is None or recipient.food_stockpile >= 20:
                continue
            if recipient.treasury < 2:
                continue
            amount = min(10, int(faction.food_stockpile // 2))
            if amount > 0:
                return neighbor.id, amount
    return None


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
        "standing_orders": [
            {
                "kind": order.kind,
                "years_left": order.years_left,
                "target_tile_id": order.target_tile_id,
            }
            for order in state.standing_orders
            if order.faction_id == faction.id
        ],
        "allowed_actions": [action.value for action in RulerAction],
    }
