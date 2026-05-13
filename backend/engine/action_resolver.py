# backend/engine/action_resolver.py
# Разделение ответственности: IntentParser, ActionExecutor, StateApplier

import json, re, random, logging
from typing import Dict, Any, List, Optional, Tuple
from .dice import calculate_damage
from world_state import WorldState
from llm_client import LLMClient

logger = logging.getLogger(__name__)

INTENT_PROMPT = """
Ты — анализатор действий в RPG. Из текста действия игрока извлеки массив JSON-объектов (даже если действие одно).
Каждый объект описывает одно намерение.
Примеры:
"использовать заклинание 'Огненный выдох' на дерево"
[{"action_type": "use_skill", "skill_name": "Огненный выдох", "target": "дерево"}]
"атаковать волка мечом"
[{"action_type": "attack", "weapon_name": "Ржавый меч", "target": "Лесной волк"}]
"осмотреть сундук, а затем идти на север"
[{"action_type": "interact", "object": "сундук"}, {"action_type": "move", "direction": "север"}]
Не добавляй пояснений, только JSON массив.
"""

REPEAT_PATTERNS = [
    re.compile(r'последовательно применяю\s+(.+?)\s+ещё\s+(\d+)\s+раз', re.IGNORECASE),
    re.compile(r'применяю\s+(.+?)\s+подряд\s+(\d+)\s+раз', re.IGNORECASE),
    re.compile(r'использую\s+(.+?)\s+ещё\s+(\d+)\s+раз', re.IGNORECASE),
    re.compile(r'повторяю\s+(.+?)\s+(\d+)\s+раз', re.IGNORECASE),
    re.compile(r'каждый раз как перезарядится[,]?\s+(.+?)\s+(\d+)\s+раз', re.IGNORECASE),
]


class IntentParser:
    """Только парсинг интентов из LLM/regex → JSON."""
    
    def __init__(self, world: WorldState, llm: LLMClient):
        self.world = world
        self.llm = llm
    
    async def extract_intents(self, player_action: str) -> List[dict]:
        # Парсим повторение без LLM
        for pattern in REPEAT_PATTERNS:
            match = pattern.search(player_action)
            if match:
                skill_phrase = match.group(1).strip()
                count = int(match.group(2))
                wait_cooldown = 'перезарядк' in player_action.lower() or 'дожидаясь' in player_action.lower()
                target_match = re.search(r'(?:на|по)\s+([а-яё]+)', player_action, re.IGNORECASE)
                target = target_match.group(1) if target_match else "цель"
                return [{
                    "action_type": "repeat_skill",
                    "skill_name": skill_phrase,
                    "target": target,
                    "count": count,
                    "wait_cooldown": wait_cooldown
                }]

        # Стандартный разбор через LLM с JSON mode (Structured Outputs)
        skills = self.world.get("characters.player.skills", [])
        skill_names = ", ".join([s["name"] for s in skills]) if skills else ""
        dynamic_prompt = INTENT_PROMPT + (f"\n\nДоступные навыки: {skill_names}" if skill_names else "")
        messages = [
            {"role": "system", "content": dynamic_prompt},
            {"role": "user", "content": player_action}
        ]
        raw = await self.llm.completion(messages, max_tokens=256, temperature=0.0, json_mode=True)
        try:
            intents = json.loads(raw)
            if isinstance(intents, list):
                return intents
            elif isinstance(intents, dict):
                return [intents]
        except Exception:
            logger.error(f"Intent parse failed: {raw}")
        # Fallback: single object
        try:
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                single = json.loads(json_match.group())
                return [single]
        except Exception:
            pass
        return [{"action_type": "other", "description": player_action}]


class ActionExecutor:
    """Проверки, расчёты, возврат изменений (не применяет к миру напрямую)."""
    
    def __init__(self, world: WorldState):
        self.world = world
    
    @staticmethod
    def _normalize_skill_name(name: str) -> str:
        name = re.sub(r'\([^)]*\)', '', name)
        name = ' '.join(name.split())
        return name.lower().strip()
    
    def _get_skill_by_name(self, name: str) -> Optional[dict]:
        skills = self.world.get("characters.player.skills", [])
        name_lower = name.lower().strip()
        # Точное совпадение
        for s in skills:
            if s["name"].lower() == name_lower:
                return s
        # Нормализованный поиск
        normalized_query = self._normalize_skill_name(name)
        best = None
        for s in skills:
            normalized_skill = self._normalize_skill_name(s["name"])
            if normalized_skill in normalized_query or normalized_query in normalized_skill:
                if best is None or len(normalized_skill) > len(self._normalize_skill_name(best["name"])):
                    best = s
        return best
    
    def _is_analyze_skill(self, skill: dict) -> bool:
        name = skill.get("name", "").lower()
        desc = skill.get("description", "").lower()
        effect = skill.get("effect", "").lower()
        category = skill.get("category", "").lower()
        analyze_keywords = [
            "анализ", "сканирование", "изучение", "исследование",
            "раскрывает уязвимости", "слабости", "слабые места",
            "+% к урону", "+20% к урону"
        ]
        full_text = name + " " + desc + " " + effect
        if any(keyword in full_text for keyword in analyze_keywords):
            return True
        if category == "знания" and ("урон" in effect or "уязвим" in effect):
            return True
        if re.search(r'\+\d+%\s+(к|крит\.? )?урон', effect):
            return True
        return False
    
    def execute_intent(self, intent: dict) -> Dict[str, Any]:
        action_type = intent.get("action_type")
        if action_type == "repeat_skill":
            # Обработка повторов требует доступа к async методам, делегируем
            return {"requires_async": True, "intent": intent}
        elif action_type == "use_skill":
            return self._handle_skill(intent)
        elif action_type == "attack":
            return self._handle_attack(intent)
        elif action_type == "interact":
            return self._handle_interact(intent)
        elif action_type == "move":
            return self._handle_move(intent)
        elif action_type == "talk":
            return self._handle_talk(intent)
        else:
            return self._handle_generic(intent)
    
    def _handle_skill(self, intent: dict) -> dict:
        skill_name = intent.get("skill_name", "").strip()
        target_name = intent.get("target", "").strip()
        skill = self._get_skill_by_name(skill_name)
        if not skill:
            return {"allowed": False, "reason": f"Навык '{skill_name}' не найден."}

        cooldowns = self.world.get("characters.player.cooldowns", {})
        cd_left = cooldowns.get(skill["name"], 0)
        if cd_left > 0:
            return {"allowed": False, "reason": f"Навык '{skill['name']}' на перезарядке ({cd_left} ходов)."}

        cost_mp = skill.get("cost_mp", 0)
        current_mp = self.world.get("characters.player.mp", 0)
        if cost_mp > current_mp:
            return {"allowed": False, "reason": f"Недостаточно MP. Нужно {cost_mp}, есть {current_mp}."}

        damage_str = skill.get("damage", "0")
        damage_type = skill.get("damage_type", "none")
        is_heal = damage_type == "heal"
        is_analyze = self._is_analyze_skill(skill)

        enemies = self.world.get("enemies", [])
        target_enemy = next((e for e in enemies if e["name"].lower() == target_name.lower()), None)
        env_objects = self.world.get("environment_objects", {})

        updates = []
        memory_entries = []
        narrator_context = {
            "skill_used": skill["name"],
            "target": target_name,
            "mp_cost": cost_mp,
            "cooldown_applied": skill.get("cooldown", 0),
        }
        system_msg = None

        # Расход MP
        new_mp = current_mp - cost_mp
        updates.append({"key": "characters.player.mp", "value": new_mp})
        narrator_context["mp_after"] = new_mp

        # Кулдаун
        if skill.get("cooldown", 0) > 0:
            new_cooldowns = dict(cooldowns)
            new_cooldowns[skill["name"]] = skill["cooldown"]
            updates.append({"key": "characters.player.cooldowns", "value": new_cooldowns})

        # Проверка баффа анализа
        analyzed = False
        if target_enemy:
            target_id = target_enemy.get("id", target_name)
            analyzed_flags = self.world.get("plot_flags.analyzed_targets", {})
            if isinstance(analyzed_flags, dict) and analyzed_flags.get(target_id):
                analyzed = True
                narrator_context["analyzed_bonus"] = True

        if is_analyze:
            if target_enemy:
                target_id = target_enemy.get("id", target_name)
                analyzed_flags = self.world.get("plot_flags.analyzed_targets", {})
                if not isinstance(analyzed_flags, dict):
                    analyzed_flags = {}
                analyzed_flags[target_id] = True
                updates.append({"key": "plot_flags.analyzed_targets", "value": analyzed_flags})
                narrator_context["analysis_applied"] = True
                memory_entries.append(f"Цель {target_name} проанализирована. +20% урона до конца боя.")
        elif is_heal:
            heal_amount, comment = calculate_damage(damage_str, self.world.get("characters.player.stats", {}))
            current_hp = self.world.get("characters.player.health", 100)
            max_hp = self.world.get("characters.player.stats.hp", 100)
            new_hp = min(current_hp + heal_amount, max_hp)
            updates.append({"key": "characters.player.health", "value": new_hp})
            narrator_context.update({"heal_amount": heal_amount, "dice_comment": comment})
            memory_entries.append(f"Исцеление {heal_amount} HP навыком {skill['name']}")
            system_msg = f"✨ {skill['name']} применён"
        else:
            dmg, comment, dmg_type = calculate_damage(damage_str, self.world.get("characters.player.stats", {}))
            dmg_type = damage_type if damage_type != "none" else dmg_type

            if analyzed:
                bonus = int(dmg * 0.2)
                dmg += bonus
                narrator_context["analysis_bonus_damage"] = bonus
                if target_enemy:
                    analyzed_flags = self.world.get("plot_flags.analyzed_targets", {})
                    if isinstance(analyzed_flags, dict):
                        analyzed_flags.pop(target_enemy.get("id", target_name), None)
                        updates.append({"key": "plot_flags.analyzed_targets", "value": analyzed_flags})

            narrator_context["damage_dealt"] = dmg
            narrator_context["damage_type"] = dmg_type
            narrator_context["dice_comment"] = comment

            if target_enemy:
                new_health = target_enemy["health"] - dmg
                idx = enemies.index(target_enemy)
                updates.append({"key": f"enemies.{idx}.health", "value": new_health})
                narrator_context["target_health_after"] = new_health
                if new_health <= 0:
                    narrator_context["target_died"] = True
                    memory_entries.append(f"Враг {target_enemy['name']} повержен")
                    system_msg = f"✨ {skill['name']} → {target_enemy['name']} повержен"
                else:
                    memory_entries.append(f"Враг {target_enemy['name']} получил {dmg} урона от {skill['name']}")
                    system_msg = f"✨ {skill['name']} применён"
            else:
                # Работа с окружением
                env_id = self._ensure_env_object(target_name, env_objects)
                current_env_health = env_objects.get(env_id, {}).get("health", 10)
                new_env_health = current_env_health - dmg
                updates.append({"key": f"environment_objects.{env_id}.health", "value": new_env_health})
                narrator_context["damage_to_environment"] = True
                narrator_context["environment_target"] = target_name
                narrator_context["environment_health"] = new_env_health
                memory_entries.append(f"Навык {skill['name']} нанёс {dmg} урона по {target_name}")
                system_msg = f"✨ {skill['name']} → 🌳 {target_name.capitalize()} получило {dmg} урона"

        # Определяем реакцию врага
        enemy_reaction = None
        if target_enemy:
            if new_health <= 0:
                enemy_reaction = "defeated"
            elif dmg >= target_enemy.get("max_health", 25) * 0.3:
                enemy_reaction = "staggered"
            else:
                enemy_reaction = "normal"

        # Формируем combat_feedback
        combat_feedback = {
            "damage_dealt": narrator_context.get("damage_dealt", 0),
            "damage_type": narrator_context.get("damage_type", "none"),
            "mp_spent": cost_mp,
            "enemy_reaction": enemy_reaction,
            "target_name": target_name
        }

        return {
            "allowed": True,
            "updates": updates,
            "memory": memory_entries,
            "narrator_context": narrator_context,
            "system_message": system_msg,
            "combat_feedback": combat_feedback
        }
    
    def _handle_attack(self, intent: dict) -> dict:
        weapon_name = intent.get("weapon_name", "").strip()
        target_name = intent.get("target", "").strip()
        inventory = self.world.get("characters.player.inventory", [])
        weapon = next((i for i in inventory if i.get("equipped") and i["name"].lower() == weapon_name.lower()), None)
        if not weapon:
            weapon = next((i for i in inventory if i.get("equipped")), None)
        if not weapon or weapon.get("type") != "weapon":
            return {"allowed": False, "reason": "Нет оружия для атаки."}

        dmg = weapon.get("damage", 5)
        if isinstance(dmg, int):
            dmg_roll = random.randint(1, dmg) + self.world.get("characters.player.stats.strength", 10)//5
        else:
            dmg_roll, _ = calculate_damage(str(dmg), self.world.get("characters.player.stats", {}))

        target_enemy = next((e for e in self.world.get("enemies", []) if e["name"].lower() == target_name.lower()), None)
        updates = []
        memory = []
        ctx = {"attack": True, "target": target_name, "weapon": weapon["name"], "damage_dealt": dmg_roll}
        sys_msg = None

        if target_enemy:
            new_hp = target_enemy["health"] - dmg_roll
            idx = self.world.get("enemies", []).index(target_enemy)
            updates.append({"key": f"enemies.{idx}.health", "value": new_hp})
            ctx["target_health_after"] = new_hp
            if new_hp <= 0:
                ctx["target_died"] = True
                memory.append(f"Враг {target_name} убит атакой оружия")
                sys_msg = f"⚔️ {target_name} повержен"
            else:
                sys_msg = f"⚔️ Атака {weapon['name']} → {target_name} получил {dmg_roll} урона"
                memory.append(f"Враг {target_name} получил {dmg_roll} урона от {weapon['name']}")
        else:
            env_id = self._ensure_env_object(target_name, self.world.get("environment_objects", {}))
            current_env_health = self.world.get(f"environment_objects.{env_id}.health", 10)
            new_env_health = current_env_health - dmg_roll
            updates.append({"key": f"environment_objects.{env_id}.health", "value": new_env_health})
            ctx["damage_to_environment"] = True
            ctx["environment_target"] = target_name
            ctx["environment_health"] = new_env_health
            memory.append(f"Атака {weapon['name']} нанесла {dmg_roll} урона по {target_name}")
            sys_msg = f"⚔️ {weapon['name']} → 🌳 {target_name.capitalize()} получило {dmg_roll} урона"

        # Определяем реакцию врага для атаки
        enemy_reaction = None
        if target_enemy and 'new_hp' in locals():
            if new_hp <= 0:
                enemy_reaction = "defeated"
            elif dmg_roll >= target_enemy.get("max_health", 25) * 0.3:
                enemy_reaction = "staggered"
            else:
                enemy_reaction = "normal"

        return {
            "allowed": True, 
            "updates": updates, 
            "memory": memory, 
            "narrator_context": ctx, 
            "system_message": sys_msg,
            "combat_feedback": {
                "damage_dealt": dmg_roll,
                "damage_type": "physical",
                "mp_spent": 0,
                "enemy_reaction": enemy_reaction,
                "target_name": target_name
            }
        }
    
    def _handle_interact(self, intent: dict) -> dict:
        obj_name = intent.get("object", "").strip()
        env_id = self._find_env_object_id(obj_name)
        updates = []
        ctx = {"interact_with": obj_name}
        sys_msg = None
        if env_id:
            env_obj = self.world.get(f"environment_objects.{env_id}", {})
            ctx["environment_health"] = env_obj.get("health", "?")
            ctx["environment_max_health"] = env_obj.get("max_health", "?")
            memory = [f"Осмотр {obj_name} (здоровье {ctx['environment_health']}/{ctx['environment_max_health']})"]
        else:
            memory = [f"Осмотр {obj_name}"]
        return {"allowed": True, "updates": updates, "memory": memory, "narrator_context": ctx, "system_message": sys_msg}
    
    def _handle_move(self, intent: dict) -> dict:
        direction = intent.get("direction", "").strip()
        current = self.world.get("location", "Лес")
        new_loc = f"{current} - {direction}"
        return {
            "allowed": True,
            "updates": [{"key": "location", "value": new_loc}],
            "memory": [f"Перемещение в {new_loc}"],
            "narrator_context": {"move_to": new_loc}
        }
    
    def _handle_talk(self, intent: dict) -> dict:
        npc = intent.get("npc", "неизвестный")
        return {
            "allowed": True,
            "updates": [],
            "memory": [f"Разговор с {npc}"],
            "narrator_context": {"talk_with": npc}
        }
    
    def _handle_generic(self, intent: dict) -> dict:
        description = intent.get("description", intent.get("text", ""))
        return {
            "allowed": True,
            "updates": [],
            "memory": [],
            "narrator_context": {"generic_action": description}
        }
    
    def _ensure_env_object(self, name: str, current_objects: dict) -> str:
        env_id = self._find_env_object_id(name)
        if not env_id:
            env_id = name.lower().replace(" ", "_")
        return env_id
    
    def _find_env_object_id(self, name: str) -> Optional[str]:
        objects = self.world.get("environment_objects", {})
        name_lower = name.lower()
        for obj_id, obj in objects.items():
            if obj.get("name", "").lower() == name_lower:
                return obj_id
        return None


class StateApplier:
    """Атомарное применение updates к WorldState."""
    
    def __init__(self, world: WorldState):
        self.world = world
        self._transaction_buffer: Optional[Dict] = None
        self._backup: Optional[Dict] = None
    
    def begin_transaction(self):
        """Начинает транзакцию — сохраняет копию состояния."""
        import copy
        self._backup = copy.deepcopy(self.world.state)
        self._transaction_buffer = {}
    
    def commit(self):
        """Применяет все накопленные изменения единым bulk_update."""
        if self._transaction_buffer:
            self.bulk_update(self._transaction_buffer)
        self._transaction_buffer = None
        self._backup = None
    
    def rollback(self):
        """Откатывает состояние к backup."""
        if self._backup:
            import copy
            self.world.state = copy.deepcopy(self._backup)
            self.world._save()
        self._transaction_buffer = None
        self._backup = None
    
    def queue_update(self, key: str, value: Any):
        """Добавляет изменение в буфер транзакции."""
        if self._transaction_buffer is not None:
            self._transaction_buffer[key] = value
        else:
            self.world.update(key, value)
    
    def bulk_update(self, updates_dict: Dict[str, Any]):
        """Применяет множество обновлений атомарно."""
        for key, value in updates_dict.items():
            self.world.update(key, value)

    # ---------- Вспомогательные методы ----------
    @staticmethod
    def _normalize_skill_name(name: str) -> str:
        name = re.sub(r'\([^)]*\)', '', name)
        name = ' '.join(name.split())
        return name.lower().strip()

    def _get_skill_by_name(self, name: str) -> Optional[dict]:
        skills = self.world.get("characters.player.skills", [])
        name_lower = name.lower().strip()
        # Точное совпадение
        for s in skills:
            if s["name"].lower() == name_lower:
                return s
        # Нормализованный поиск
        normalized_query = self._normalize_skill_name(name)
        best = None
        for s in skills:
            normalized_skill = self._normalize_skill_name(s["name"])
            if normalized_skill in normalized_query or normalized_query in normalized_skill:
                if best is None or len(normalized_skill) > len(self._normalize_skill_name(best["name"])):
                    best = s
        return best

    def _is_analyze_skill(self, skill: dict) -> bool:
        name = skill.get("name", "").lower()
        desc = skill.get("description", "").lower()
        effect = skill.get("effect", "").lower()
        category = skill.get("category", "").lower()
        analyze_keywords = [
            "анализ", "сканирование", "изучение", "исследование",
            "раскрывает уязвимости", "слабости", "слабые места",
            "+% к урону", "+20% к урону"
        ]
        full_text = name + " " + desc + " " + effect
        if any(keyword in full_text for keyword in analyze_keywords):
            return True
        if category == "знания" and ("урон" in effect or "уязвим" in effect):
            return True
        if re.search(r'\+\d+%\s+(к|крит\.? )?урон', effect):
            return True
        return False

    # ---------- Парсинг намерений ----------
    async def extract_intents(self, player_action: str) -> List[dict]:
        # Парсим повторение без LLM
        for pattern in REPEAT_PATTERNS:
            match = pattern.search(player_action)
            if match:
                skill_phrase = match.group(1).strip()
                count = int(match.group(2))
                wait_cooldown = 'перезарядк' in player_action.lower() or 'дожидаясь' in player_action.lower()
                target_match = re.search(r'(?:на|по)\s+([а-яё]+)', player_action, re.IGNORECASE)
                target = target_match.group(1) if target_match else "цель"
                return [{
                    "action_type": "repeat_skill",
                    "skill_name": skill_phrase,
                    "target": target,
                    "count": count,
                    "wait_cooldown": wait_cooldown
                }]

        # Стандартный разбор через LLM
        skills = self.world.get("characters.player.skills", [])
        skill_names = ", ".join([s["name"] for s in skills]) if skills else ""
        dynamic_prompt = INTENT_PROMPT + (f"\n\nДоступные навыки: {skill_names}" if skill_names else "")
        messages = [
            {"role": "system", "content": dynamic_prompt},
            {"role": "user", "content": player_action}
        ]
        raw = await self.llm.completion(messages, max_tokens=256, temperature=0.0)
        try:
            start = raw.find('[')
            end = raw.rfind(']')
            if start != -1 and end != -1:
                json_str = raw[start:end+1]
                intents = json.loads(json_str)
                if isinstance(intents, list):
                    return intents
        except Exception:
            logger.error(f"Intent parse failed: {raw}")
        # Fallback: single object
        try:
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                single = json.loads(json_match.group())
                return [single]
        except Exception:
            pass
        return [{"action_type": "other", "description": player_action}]

    # ---------- Обработка всех намерений ----------
    async def resolve_all(self, player_action: str) -> Dict[str, Any]:
        intents = await self.extract_intents(player_action)
        if not intents:
            intents = [{"action_type": "other", "description": player_action}]

        combined = {
            "allowed": True,
            "updates": [],
            "memory": [],
            "narrator_contexts": [],
            "system_messages": [],
            "repeat_count": 0
        }

        for intent in intents:
            action_type = intent.get("action_type")
            if action_type == "repeat_skill":
                result = await self._handle_repeat_skill(intent)
            elif action_type == "use_skill":
                result = self._handle_skill(intent)
            elif action_type == "attack":
                result = self._handle_attack(intent)
            elif action_type == "interact":
                result = self._handle_interact(intent)
            elif action_type == "move":
                result = self._handle_move(intent)
            elif action_type == "talk":
                result = self._handle_talk(intent)
            else:
                result = self._handle_generic(intent)

            if not result["allowed"]:
                return result

            combined["updates"].extend(result.get("updates", []))
            combined["memory"].extend(result.get("memory", []))
            if "narrator_context" in result:
                combined["narrator_contexts"].append(result["narrator_context"])
            if "system_message" in result:
                combined["system_messages"].append(result["system_message"])
            if action_type == "repeat_skill":
                combined["repeat_count"] = intent.get("count", 1)

        return combined

    # ---------- Обработка конкретных действий ----------
    def _handle_skill(self, intent: dict) -> dict:
        skill_name = intent.get("skill_name", "").strip()
        target_name = intent.get("target", "").strip()
        skill = self._get_skill_by_name(skill_name)
        if not skill:
            return {"allowed": False, "reason": f"Навык '{skill_name}' не найден."}

        cooldowns = self.world.get("characters.player.cooldowns", {})
        cd_left = cooldowns.get(skill["name"], 0)
        if cd_left > 0:
            return {"allowed": False, "reason": f"Навык '{skill['name']}' на перезарядке ({cd_left} ходов)."}

        cost_mp = skill.get("cost_mp", 0)
        current_mp = self.world.get("characters.player.mp", 0)
        if cost_mp > current_mp:
            return {"allowed": False, "reason": f"Недостаточно MP. Нужно {cost_mp}, есть {current_mp}."}

        damage_str = skill.get("damage", "0")
        damage_type = skill.get("damage_type", "none")
        is_heal = damage_type == "heal"
        is_analyze = self._is_analyze_skill(skill)

        enemies = self.world.get("enemies", [])
        target_enemy = next((e for e in enemies if e["name"].lower() == target_name.lower()), None)
        env_objects = self.world.get("environment_objects", {})

        updates = []
        memory_entries = []
        narrator_context = {
            "skill_used": skill["name"],
            "target": target_name,
            "mp_cost": cost_mp,
            "cooldown_applied": skill.get("cooldown", 0),
        }
        system_msg = None

        # Расход MP
        new_mp = current_mp - cost_mp
        updates.append({"key": "characters.player.mp", "value": new_mp})
        narrator_context["mp_after"] = new_mp

        # Кулдаун
        if skill.get("cooldown", 0) > 0:
            new_cooldowns = dict(cooldowns)
            new_cooldowns[skill["name"]] = skill["cooldown"]
            updates.append({"key": "characters.player.cooldowns", "value": new_cooldowns})

        # Проверка баффа анализа
        analyzed = False
        if target_enemy:
            target_id = target_enemy.get("id", target_name)
            analyzed_flags = self.world.get("plot_flags.analyzed_targets", {})
            if isinstance(analyzed_flags, dict) and analyzed_flags.get(target_id):
                analyzed = True
                narrator_context["analyzed_bonus"] = True

        if is_analyze:
            if target_enemy:
                target_id = target_enemy.get("id", target_name)
                analyzed_flags = self.world.get("plot_flags.analyzed_targets", {})
                if not isinstance(analyzed_flags, dict):
                    analyzed_flags = {}
                analyzed_flags[target_id] = True
                updates.append({"key": "plot_flags.analyzed_targets", "value": analyzed_flags})
                narrator_context["analysis_applied"] = True
                memory_entries.append(f"Цель {target_name} проанализирована. +20% урона до конца боя.")
        elif is_heal:
            heal_amount, comment = calculate_damage(damage_str, self.world.get("characters.player.stats", {}))
            current_hp = self.world.get("characters.player.health", 100)
            max_hp = self.world.get("characters.player.stats.hp", 100)
            new_hp = min(current_hp + heal_amount, max_hp)
            updates.append({"key": "characters.player.health", "value": new_hp})
            narrator_context.update({"heal_amount": heal_amount, "dice_comment": comment})
            memory_entries.append(f"Исцеление {heal_amount} HP навыком {skill['name']}")
            system_msg = f"✨ {skill['name']} применён"
        else:
            dmg, comment, dmg_type = calculate_damage(damage_str, self.world.get("characters.player.stats", {}))
            dmg_type = damage_type if damage_type != "none" else dmg_type

            if analyzed:
                bonus = int(dmg * 0.2)
                dmg += bonus
                narrator_context["analysis_bonus_damage"] = bonus
                if target_enemy:
                    analyzed_flags = self.world.get("plot_flags.analyzed_targets", {})
                    if isinstance(analyzed_flags, dict):
                        analyzed_flags.pop(target_enemy.get("id", target_name), None)
                        updates.append({"key": "plot_flags.analyzed_targets", "value": analyzed_flags})

            narrator_context["damage_dealt"] = dmg
            narrator_context["damage_type"] = dmg_type
            narrator_context["dice_comment"] = comment

            if target_enemy:
                new_health = target_enemy["health"] - dmg
                idx = enemies.index(target_enemy)
                updates.append({"key": f"enemies.{idx}.health", "value": new_health})
                narrator_context["target_health_after"] = new_health
                if new_health <= 0:
                    narrator_context["target_died"] = True
                    memory_entries.append(f"Враг {target_enemy['name']} повержен")
                    system_msg = f"✨ {skill['name']} → {target_enemy['name']} повержен"
                else:
                    memory_entries.append(f"Враг {target_enemy['name']} получил {dmg} урона от {skill['name']}")
                    system_msg = f"✨ {skill['name']} применён"
            else:
                # Работа с окружением
                env_id = self._ensure_env_object(target_name, env_objects)
                current_env_health = env_objects.get(env_id, {}).get("health", 10)
                new_env_health = current_env_health - dmg
                updates.append({"key": f"environment_objects.{env_id}.health", "value": new_env_health})
                narrator_context["damage_to_environment"] = True
                narrator_context["environment_target"] = target_name
                narrator_context["environment_health"] = new_env_health
                memory_entries.append(f"Навык {skill['name']} нанёс {dmg} урона по {target_name}")
                system_msg = f"✨ {skill['name']} → 🌳 {target_name.capitalize()} получило {dmg} урона"

        if not system_msg:
            system_msg = f"✨ {skill['name']} применён"

        return {
            "allowed": True,
            "updates": updates,
            "memory": memory_entries,
            "narrator_context": narrator_context,
            "system_message": system_msg
        }

    def _handle_attack(self, intent: dict) -> dict:
        weapon_name = intent.get("weapon_name", "").strip()
        target_name = intent.get("target", "").strip()
        inventory = self.world.get("characters.player.inventory", [])
        weapon = next((i for i in inventory if i.get("equipped") and i["name"].lower() == weapon_name.lower()), None)
        if not weapon:
            weapon = next((i for i in inventory if i.get("equipped")), None)
        if not weapon or weapon.get("type") != "weapon":
            return {"allowed": False, "reason": "Нет оружия для атаки."}

        dmg = weapon.get("damage", 5)
        if isinstance(dmg, int):
            dmg_roll = random.randint(1, dmg) + self.world.get("characters.player.stats.strength", 10)//5
        else:
            dmg_roll, _ = calculate_damage(str(dmg), self.world.get("characters.player.stats", {}))

        target_enemy = next((e for e in self.world.get("enemies", []) if e["name"].lower() == target_name.lower()), None)
        updates = []
        memory = []
        ctx = {"attack": True, "target": target_name, "weapon": weapon["name"], "damage_dealt": dmg_roll}
        sys_msg = None

        if target_enemy:
            new_hp = target_enemy["health"] - dmg_roll
            idx = self.world.get("enemies", []).index(target_enemy)
            updates.append({"key": f"enemies.{idx}.health", "value": new_hp})
            ctx["target_health_after"] = new_hp
            if new_hp <= 0:
                ctx["target_died"] = True
                memory.append(f"Враг {target_name} убит атакой оружия")
                sys_msg = f"⚔️ {target_name} повержен"
            else:
                sys_msg = f"⚔️ Атака {weapon['name']} → {target_name} получил {dmg_roll} урона"
                memory.append(f"Враг {target_name} получил {dmg_roll} урона от {weapon['name']}")
        else:
            env_id = self._ensure_env_object(target_name, self.world.get("environment_objects", {}))
            current_env_health = self.world.get(f"environment_objects.{env_id}.health", 10)
            new_env_health = current_env_health - dmg_roll
            updates.append({"key": f"environment_objects.{env_id}.health", "value": new_env_health})
            ctx["damage_to_environment"] = True
            ctx["environment_target"] = target_name
            ctx["environment_health"] = new_env_health
            memory.append(f"Атака {weapon['name']} нанесла {dmg_roll} урона по {target_name}")
            sys_msg = f"⚔️ {weapon['name']} → 🌳 {target_name.capitalize()} получило {dmg_roll} урона"

        return {"allowed": True, "updates": updates, "memory": memory, "narrator_context": ctx, "system_message": sys_msg}

    def _handle_interact(self, intent: dict) -> dict:
        obj_name = intent.get("object", "").strip()
        env_id = self._find_env_object_id(obj_name)
        updates = []
        ctx = {"interact_with": obj_name}
        sys_msg = None
        if env_id:
            env_obj = self.world.get(f"environment_objects.{env_id}", {})
            ctx["environment_health"] = env_obj.get("health", "?")
            ctx["environment_max_health"] = env_obj.get("max_health", "?")
            memory = [f"Осмотр {obj_name} (здоровье {ctx['environment_health']}/{ctx['environment_max_health']})"]
        else:
            memory = [f"Осмотр {obj_name}"]
        return {"allowed": True, "updates": updates, "memory": memory, "narrator_context": ctx, "system_message": sys_msg}

    # ---------- Обработка повторений ----------
    async def _handle_repeat_skill(self, intent: dict) -> dict:
        skill_name = intent["skill_name"]
        target = intent["target"]
        count = intent["count"]
        wait_cooldown = intent["wait_cooldown"]

        skill = self._get_skill_by_name(skill_name)
        if not skill:
            return {"allowed": False, "reason": f"Навык '{skill_name}' не найден."}

        # Проверяем первое применение
        first_result = self._handle_skill({"skill_name": skill["name"], "target": target})
        if not first_result["allowed"]:
            return first_result

        # Первое применение успешно
        combined_updates = first_result["updates"][:]
        combined_memory = first_result["memory"][:]
        combined_contexts = [first_result["narrator_context"]]
        system_msgs = [first_result.get("system_message", f"✨ {skill['name']} применён (1/{count})")]
        total_dmg = first_result["narrator_context"].get("damage_dealt", 0)

        # Для простоты сразу применяем обновления первого раза, чтобы дальше считать ресурсы
        for upd in first_result["updates"]:
            self.world.update(upd["key"], upd["value"])

        successful = 1
        while successful < count:
            # Если нужно ждать кулдаун, уменьшаем его до 0, симулируя ходы
            if wait_cooldown:
                while True:
                    cd = self.world.get("characters.player.cooldowns", {}).get(skill["name"], 0)
                    if cd <= 0:
                        break
                    self.world.reduce_cooldowns()
                    self.world.apply_passive_regen()
            else:
                cd = self.world.get("characters.player.cooldowns", {}).get(skill["name"], 0)
                if cd > 0:
                    system_msgs.append(f"⏳ Навык на перезарядке, ожидайте.")
                    break

            # Повторное применение
            result = self._handle_skill({"skill_name": skill["name"], "target": target})
            if not result["allowed"]:
                system_msgs.append(f"❌ {result['reason']} (после {successful} применений)")
                break

            combined_updates.extend(result["updates"])
            combined_memory.extend(result["memory"])
            if "narrator_context" in result:
                combined_contexts.append(result["narrator_context"])
            system_msgs.append(result.get("system_message", f"✨ {skill['name']} применён ({successful+1}/{count})"))
            total_dmg += result["narrator_context"].get("damage_dealt", 0)
            successful += 1

        # Итоговый контекст для нарратива
        final_narrator_context = {
            "repeat_summary": f"Навык {skill['name']} использован {successful} раз(а) по {target}",
            "total_damage": total_dmg,
            "applications": successful,
            "target": target
        }
        combined_contexts.append(final_narrator_context)

        return {
            "allowed": True,
            "updates": combined_updates,
            "memory": combined_memory,
            "narrator_contexts": combined_contexts,
            "system_messages": system_msgs,
            "repeat_count": count
        }

    # Вспомогательные методы окружения
    def _ensure_env_object(self, name: str, current_objects: dict) -> str:
        """Создаёт или возвращает id объекта окружения с начальным здоровьем."""
        env_id = self._find_env_object_id(name)
        if not env_id:
            env_id = name.lower().replace(" ", "_")
            self.world.update(f"environment_objects.{env_id}", {
                "name": name,
                "health": 20,
                "max_health": 20
            })
        return env_id

    def _find_env_object_id(self, name: str) -> Optional[str]:
        objects = self.world.get("environment_objects", {})
        name_lower = name.lower()
        for obj_id, obj in objects.items():
            if obj.get("name", "").lower() == name_lower:
                return obj_id
        return None

    # Остальные обработчики без изменений
    def _handle_move(self, intent: dict) -> dict:
        direction = intent.get("direction", "").strip()
        current = self.world.get("location", "Лес")
        new_loc = f"{current} - {direction}"
        return {
            "allowed": True,
            "updates": [{"key": "location", "value": new_loc}],
            "memory": [f"Перемещение в {new_loc}"],
            "narrator_context": {"move_to": new_loc}
        }

    def _handle_talk(self, intent: dict) -> dict:
        npc = intent.get("npc", "неизвестный")
        return {
            "allowed": True,
            "updates": [],
            "memory": [f"Разговор с {npc}"],
            "narrator_context": {"talk_with": npc}
        }

    def _handle_generic(self, intent: dict) -> dict:
        description = intent.get("description", intent.get("text", ""))
        return {
            "allowed": True,
            "updates": [],
            "memory": [],
            "narrator_context": {"generic_action": description}
        }