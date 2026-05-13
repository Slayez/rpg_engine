# backend/engine/world_updater.py

import json
import logging
from typing import TYPE_CHECKING
from system_prompt import UPDATE_GENERATOR_PROMPT
from json_utils import extract_json

if TYPE_CHECKING:
    from .narrative_engine import NarrativeEngine

logger = logging.getLogger(__name__)

class WorldUpdater:
    def __init__(self, engine: "NarrativeEngine"):
        self.engine = engine

    async def generate_updates(self, narration: str, player_action: str) -> dict:
        world = self.engine.world
        stats = world.get("characters.player.stats", {})
        skills = world.get("characters.player.skills", [])
        inventory = world.get("characters.player.inventory", [])
        enemies = world.get("enemies", [])
        active_quests = world.get("active_quests", [])
        plot_flags = world.get("plot_flags", {})
        location = world.get("location", "forest")
        cooldowns = world.get("characters.player.cooldowns", {})

        context = (
            f"Нарратив:\n{narration}\n\n"
            f"Действие игрока: {player_action}\n"
            f"Текущие статы: {json.dumps(stats, ensure_ascii=False)}\n"
            f"Навыки: {json.dumps(skills, ensure_ascii=False)}\n"
            f"Кулдауны: {json.dumps(cooldowns, ensure_ascii=False)}\n"
            f"Инвентарь: {json.dumps(inventory, ensure_ascii=False)}\n"
            f"Враги: {json.dumps(enemies, ensure_ascii=False)}\n"
            f"Квесты: {json.dumps(active_quests, ensure_ascii=False)}\n"
            f"Сюжетные флаги: {json.dumps(plot_flags, ensure_ascii=False)}\n"
            f"Локация: {location}"
        )
        messages = [
            {"role": "system", "content": UPDATE_GENERATOR_PROMPT},
            {"role": "user", "content": context}
        ]
        raw = await self.engine.llm.completion(messages, max_tokens=512, temperature=0.3)
        try:
            return extract_json(raw)
        except:
            logger.error("Update generation failed to parse JSON")
            return {"world_updates": [], "memory_entries": []}

    def apply_updates(self, narration: str, updates: list, memory_entries: list, player_action: str):
        # сохраняем чекпойнт
        self.engine._save_checkpoint()

        world = self.engine.world
        for upd in updates:
            if "action" in upd:
                # не даём LLM менять кулдауны
                if upd.get("key", "").startswith("characters.player.cooldowns"):
                    continue
                world.atomic_update(upd)
            else:
                key = upd.get("key", "")
                if key.startswith("characters.player.cooldowns"):
                    continue
                # health и mp контролируются enforce_resource_limits
                world.update(key, upd["value"])

        # гарантируем ограничения
        world.enforce_resource_limits()

        # добавляем память
        mem_ids = []
        for mem in memory_entries:
            mem_id = self.engine.memory.add_memory(mem, {"location": world.get("location")})
            mem_ids.append(mem_id)
        self.engine.action_stack[-1]['memory_ids'] = mem_ids

        # история
        self.engine.add_to_history("user", player_action)
        self.engine.add_to_history("assistant", narration)
        messages_snapshot = [
            {"sender": "user" if m["role"] == "user" else "assistant", "text": m["content"]}
            for m in self.engine.history
        ]
        world.update("chat_history", messages_snapshot)