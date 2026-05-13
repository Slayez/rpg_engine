# backend/engine/narration.py

import json
import logging
from typing import TYPE_CHECKING, List
from system_prompt import NARRATOR_PROMPT
from models import AVAILABLE_RACES

if TYPE_CHECKING:
    from .narrative_engine import NarrativeEngine

logger = logging.getLogger(__name__)

class NarrationGenerator:
    def __init__(self, engine: "NarrativeEngine"):
        self.engine = engine

    def build_context(self, player_action: str) -> str:
        world = self.engine.world
        memory = self.engine.memory

        world_json = json.dumps(world.relevant_snapshot(player_action), ensure_ascii=False)
        stats = world.get("characters.player.stats", {})
        stats_text = json.dumps(stats, ensure_ascii=False)
        skills = world.get("characters.player.skills", [])
        skills_text = "\n".join(
            f"- {s['name']} (ур.{s['level']}): {s.get('description','')}"
            for s in skills
        ) or "нет"
        memory_entries = memory.query_memory(player_action, n_results=3)
        memory_text = "\n".join(f"- {m}" for m in memory_entries) or "пусто"
        recent_history = "\n".join(
            f"{'Игрок' if m['role']=='user' else 'Мастер'}: {m['content']}"
            for m in self.engine.history[-10:]
        )
        race_id = world.get("characters.player.race", "human")
        race = next((r for r in AVAILABLE_RACES if r.id == race_id), None)
        race_info = f"Раса: {race.name if race else 'Неизвестная'}. {race.physical_traits if race else ''}"
        cooldowns = world.get("characters.player.cooldowns", {})
        cd_text = ", ".join(f"{k}: {v} хд" for k, v in cooldowns.items()) or "нет"
        return (
            f"Мир:\n{world_json}\n\n"
            f"{race_info}\n\n"
            f"Кулдауны: {cd_text}\n\n"
            f"Статы:\n{stats_text}\n\n"
            f"Навыки:\n{skills_text}\n\n"
            f"Память:\n{memory_text}\n\n"
            f"История:\n{recent_history}\n\n"
            f"Действие игрока: {player_action}"
        )

    async def generate_from_result(self, player_action: str, narrator_contexts: List[dict]) -> str:
        """
        Генерирует нарратив на основе списка контекстов (возможно, от нескольких намерений).
        """
        world = self.engine.world
        # Объединяем контексты в читаемый текст
        mech_text = ""
        for i, ctx in enumerate(narrator_contexts, 1):
            mech_text += f"\nДействие {i}: {json.dumps(ctx, ensure_ascii=False)}"

        stats = world.get("characters.player.stats", {})
        context = (
            f"Действие игрока: {player_action}\n"
            f"Результаты механики (справочно):\n{mech_text}\n\n"
            f"Текущие статы: {json.dumps(stats, ensure_ascii=False)}\n"
            f"Локация: {world.get('location')}\n"
        )
        messages = [
            {"role": "system", "content": NARRATOR_PROMPT},
            {"role": "user", "content": context}
        ]
        return await self.engine.llm.completion(messages, max_tokens=1024, temperature=0.7)