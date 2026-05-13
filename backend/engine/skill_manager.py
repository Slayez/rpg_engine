# backend/engine/skill_manager.py

import logging
from typing import Dict
from world_state import WorldState

logger = logging.getLogger(__name__)

class SkillManager:
    """Логика применения навыков: поиск, кулдауны, расход MP."""

    def __init__(self, world: WorldState):
        self.world = world

    def try_use_skill(self, action_text: str) -> Dict:
        """
        Возвращает:
          - skill_used: bool
          - skill_name: str | None
          - error: str | None (если не удалось применить)
          - mp_cost: int (если успешно)
          - cooldown_set: int (если успешно)
        При успехе MP уже вычтены, кулдаун установлен.
        """
        skills = self.world.get("characters.player.skills", [])
        if not skills:
            return {"skill_used": False}

        action_lower = action_text.lower()
        matched_skill = None
        for skill in skills:
            if skill["name"].lower() in action_lower:
                # выбираем самое длинное совпадение, чтобы избежать частичных совпадений
                if matched_skill is None or len(skill["name"]) > len(matched_skill["name"]):
                    matched_skill = skill

        if not matched_skill:
            return {"skill_used": False}

        skill_name = matched_skill["name"]
        cooldowns = self.world.get("characters.player.cooldowns", {})
        current_cd = cooldowns.get(skill_name, 0)
        if current_cd > 0:
            return {
                "skill_used": True,
                "skill_name": skill_name,
                "error": f"Навык '{skill_name}' ещё не готов (кулдаун: {current_cd} ходов)."
            }

        cost_mp = matched_skill.get("cost_mp", 0)
        current_mp = self.world.get("characters.player.mp", 0)
        if cost_mp > current_mp:
            return {
                "skill_used": True,
                "skill_name": skill_name,
                "error": f"Недостаточно MP. Требуется {cost_mp}, у вас {current_mp}."
            }

        # Применяем
        self.world.update("characters.player.mp", current_mp - cost_mp)
        cooldown_value = matched_skill.get("cooldown", 0)
        if cooldown_value > 0:
            new_cooldowns = {**cooldowns, skill_name: cooldown_value}
            self.world.update("characters.player.cooldowns", new_cooldowns)

        return {
            "skill_used": True,
            "skill_name": skill_name,
            "mp_cost": cost_mp,
            "cooldown_set": cooldown_value
        }