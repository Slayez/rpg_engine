# backend/engine/validation.py

import json
import re
import logging
from typing import TYPE_CHECKING
from system_prompt import VALIDATOR_PROMPT, VALIDATOR_DIFFICULTY_PROMPT
from models import AVAILABLE_RACES

if TYPE_CHECKING:
    from .narrative_engine import NarrativeEngine

logger = logging.getLogger(__name__)

class ActionValidator:
    def __init__(self, engine: "NarrativeEngine"):
        self.engine = engine

    async def validate(self, player_action: str) -> dict:
        world = self.engine.world
        race_id = world.get("characters.player.race", "human")
        race = next((r for r in AVAILABLE_RACES if r.id == race_id), None)
        race_info = f"{race.name if race else 'Неизвестная'}: {race.physical_traits if race else ''}"
        stats = world.get("characters.player.stats", {})
        skills = world.get("characters.player.skills", [])
        skill_names = [s["name"].lower() for s in skills]
        inventory = world.get("characters.player.inventory", [])
        item_names = [item["name"].lower() for item in inventory]
        location = world.get("location", "лес")
        enemies = world.get("enemies", [])
        enemy_names = [e["name"].lower() for e in enemies]
        plot_flags = world.get("plot_flags", {})
        cooldowns = world.get("characters.player.cooldowns", {})

        context = (
            f"Раса: {race_info}\n"
            f"Характеристики: {json.dumps(stats, ensure_ascii=False)}\n"
            f"Навыки: {', '.join(skill_names) if skill_names else 'нет'}\n"
            f"Кулдауны: {json.dumps(cooldowns)}\n"
            f"Инвентарь: {', '.join(item_names) if item_names else 'пуст'}\n"
            f"Враги в локации: {', '.join(enemy_names) if enemy_names else 'нет'}\n"
            f"Местоположение: {location}\n"
            f"Сюжетные флаги: {json.dumps(plot_flags, ensure_ascii=False)}\n"
            f"Действие игрока: {player_action}"
        )
        messages = [
            {"role": "system", "content": VALIDATOR_PROMPT},
            {"role": "user", "content": context}
        ]
        try:
            response_text = await self.engine.llm.completion(messages, max_tokens=256, temperature=0.2)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                logger.info(f"Validation: {result}")
                return {
                    "allowed": result.get("allowed", True),
                    "reason": result.get("reason", ""),
                    "modified_action": result.get("modified_action", "")
                }
        except Exception as e:
            logger.error(f"Validator error: {e}")
        return {"allowed": True, "reason": "", "modified_action": ""}

    async def validate_difficulty(self, player_action: str) -> dict:
        world = self.engine.world
        context = (
            f"Действие: {player_action}\n"
            f"Статы: {json.dumps(world.get('characters.player.stats', {}), ensure_ascii=False)}\n"
            f"Локация: {world.get('location')}, сюжет: {json.dumps(world.get('plot_flags', {}), ensure_ascii=False)}"
        )
        messages = [
            {"role": "system", "content": VALIDATOR_DIFFICULTY_PROMPT},
            {"role": "user", "content": context}
        ]
        try:
            resp = await self.engine.llm.completion(messages, max_tokens=100, temperature=0.1)
            out = json.loads(re.search(r'\{.*\}', resp, re.DOTALL).group())
            return out
        except:
            return {"success_chance": 50, "loot_rarity": "common"}