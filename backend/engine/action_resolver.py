# backend/engine/action_resolver.py
import json, re, random, logging, copy
from typing import Dict, Any, List, Optional
from .dice import calculate_damage
from world_state import WorldState
from llm_client import LLMClient
from json_utils import parse_intents

logger = logging.getLogger(__name__)

INTENT_PROMPT = """
Ты — анализатор действий в RPG. Из текста действия игрока извлеки массив JSON-объектов.
Каждый объект описывает одно намерение.
Примеры:
"использовать заклинание 'Огненный шар' на волка" -> [{"action_type": "use_skill", "skill_name": "Огненный шар", "target": "Лесной волк"}]
"атаковать волка мечом" -> [{"action_type": "attack", "weapon_name": "Ржавый меч", "target": "Лесной волк"}]
Не добавляй пояснений, только JSON массив.
"""

REPEAT_PATTERNS = [
    re.compile(r'последовательно применяю\s+(.+?)\s+ещё\s+(\d+)\s+раз', re.IGNORECASE),
    re.compile(r'применяю\s+(.+?)\s+подряд\s+(\d+)\s+раз', re.IGNORECASE),
    re.compile(r'использую\s+(.+?)\s+ещё\s+(\d+)\s+раз', re.IGNORECASE),
    re.compile(r'повторяю\s+(.+?)\s+(\d+)\s+раз', re.IGNORECASE),
]

class IntentParser:
    def __init__(self, world: WorldState, llm: LLMClient):
        self.world = world
        self.llm = llm

    async def extract_intents(self, player_action: str) -> List[dict]:
        for pattern in REPEAT_PATTERNS:
            match = pattern.search(player_action)
            if match:
                return [{
                    "action_type": "repeat_skill",
                    "skill_name": match.group(1).strip(),
                    "target": "цель",
                    "count": int(match.group(2)),
                    "wait_cooldown": 'перезарядк' in player_action.lower()
                }]

        skills = self.world.get("characters.player.skills", [])
        skill_names = ", ".join([s["name"] for s in skills]) if skills else ""
        messages = [
            {"role": "system", "content": INTENT_PROMPT + (f"\nДоступные навыки: {skill_names}" if skill_names else "")},
            {"role": "user", "content": player_action}
        ]
        raw = await self.llm.completion(messages, max_tokens=256, temperature=0.0, json_mode=True)
        intents = parse_intents(raw)

        # FALLBACK: Если LLM вернул "other", ищем навык/атаку по ключевым словам
        if len(intents) == 1 and intents[0].get("action_type") == "other":
            action_lower = player_action.lower()
            available_skills = self.world.get("characters.player.skills", [])
            for skill in available_skills:
                if skill["name"].lower() in action_lower:
                    target = "враг"
                    for enemy in self.world.get("enemies", []):
                        if enemy["name"].lower() in action_lower:
                            target = enemy["name"]
                            break
                    return [{"action_type": "use_skill", "skill_name": skill["name"], "target": target}]
            if any(w in action_lower for w in ["атак", "удар", "бью", "режу", "стреляю", "кидаю", "огненн", "шар"]):
                target = "враг"
                for enemy in self.world.get("enemies", []):
                    if enemy["name"].lower() in action_lower:
                        target = enemy["name"]
                        break
                return [{"action_type": "attack", "target": target}]
        return intents

class ActionExecutor:
    def __init__(self, world: WorldState):
        self.world = world

    @staticmethod
    def _normalize_skill_name(name: str) -> str:
        return ' '.join(re.sub(r'\([^)]*\)', '', name).split()).lower().strip()

    def _get_skill_by_name(self, name: str) -> Optional[dict]:
        skills = self.world.get("characters.player.skills", [])
        name_lower = name.lower().strip()
        for s in skills:
            if s["name"].lower() == name_lower: return s
        normalized_query = self._normalize_skill_name(name)
        best = None
        for s in skills:
            ns = self._normalize_skill_name(s["name"])
            if ns in normalized_query or normalized_query in ns:
                if best is None or len(ns) > len(self._normalize_skill_name(best["name"])): best = s
        return best

    def execute_intent(self, intent: dict) -> Dict[str, Any]:
        action_type = intent.get("action_type")
        if action_type == "use_skill": return self._handle_skill(intent)
        elif action_type == "attack": return self._handle_attack(intent)
        elif action_type == "interact": return self._handle_interact(intent)
        elif action_type == "move": return self._handle_move(intent)
        elif action_type == "talk": return self._handle_talk(intent)
        else: return self._handle_generic(intent)

    def _handle_skill(self, intent: dict) -> dict:
        skill_name = intent.get("skill_name", "").strip()
        target_name = intent.get("target", "").strip()
        skill = self._get_skill_by_name(skill_name)
        if not skill: return {"allowed": False, "reason": f"Навык '{skill_name}' не найден."}
        
        cooldowns = self.world.get("characters.player.cooldowns", {})
        if cooldowns.get(skill["name"], 0) > 0:
            return {"allowed": False, "reason": f"Навык '{skill['name']}' на перезарядке."}
            
        cost_mp = skill.get("cost_mp", 0)
        current_mp = self.world.get("characters.player.mp", 0)
        if cost_mp > current_mp:
            return {"allowed": False, "reason": f"Недостаточно MP. Нужно {cost_mp}, есть {current_mp}."}

        damage_str = skill.get("damage", "0")
        damage_type = skill.get("damage_type", "none")
        is_heal = damage_type == "heal"
        enemies = self.world.get("enemies", [])
        target_enemy = next((e for e in enemies if e["name"].lower() == target_name.lower()), None)
        
        updates = []
        memory_entries = []
        narrator_context = {"skill_used": skill["name"], "target": target_name, "mp_cost": cost_mp}
        
        # Расход MP
        new_mp = current_mp - cost_mp
        updates.append({"key": "characters.player.mp", "value": new_mp})
        
        # Кулдаун
        if skill.get("cooldown", 0) > 0:
            new_cd = dict(cooldowns)
            new_cd[skill["name"]] = skill["cooldown"]
            updates.append({"key": "characters.player.cooldowns", "value": new_cd})
            
        combat_feedback = {"damage_dealt": 0, "mp_spent": cost_mp, "enemy_reaction": None, "target_name": target_name}
        
        if is_heal:
            # ✅ ИСПРАВЛЕНО: распаковка 3 значений
            heal_amt, heal_comment, _ = calculate_damage(damage_str, self.world.get("characters.player.stats", {}))
            cur_hp = self.world.get("characters.player.health", 100)
            max_hp = self.world.get("characters.player.stats.hp", 100)
            new_hp = min(cur_hp + heal_amt, max_hp)
            updates.append({"key": "characters.player.health", "value": new_hp})
            narrator_context["heal_amount"] = heal_amt
            narrator_context["dice_comment"] = heal_comment
            combat_feedback["heal_amount"] = heal_amt
            memory_entries.append(f"Исцеление {heal_amt} HP навыком {skill['name']}")
        else:
            # ✅ ИСПРАВЛЕНО: распаковка 3 значений
            dmg, dmg_comment, calc_type = calculate_damage(damage_str, self.world.get("characters.player.stats", {}))
            final_type = damage_type if damage_type != "none" else calc_type
            narrator_context["damage_dealt"] = dmg
            narrator_context["damage_type"] = final_type
            narrator_context["dice_comment"] = dmg_comment
            combat_feedback["damage_dealt"] = dmg
            combat_feedback["damage_type"] = final_type
            
            if target_enemy:
                new_hp = max(0, target_enemy["health"] - dmg)
                idx = enemies.index(target_enemy)
                updates.append({"key": f"enemies.{idx}.health", "value": new_hp})
                narrator_context["target_health_after"] = new_hp
                combat_feedback["target_health_after"] = new_hp
                if new_hp <= 0:
                    narrator_context["target_died"] = True
                    combat_feedback["enemy_reaction"] = "defeated"
                    memory_entries.append(f"Враг {target_enemy['name']} повержен")
                else:
                    combat_feedback["enemy_reaction"] = "staggered" if dmg >= target_enemy.get("max_health", 25) * 0.3 else "normal"
                    memory_entries.append(f"Враг {target_enemy['name']} получил {dmg} урона")

        return {
            "allowed": True, "updates": updates, "memory": memory_entries,
            "narrator_context": narrator_context, "system_message": f"✨ {skill['name']} применён",
            "combat_feedback": combat_feedback
        }

    def _handle_attack(self, intent: dict) -> dict:
        target_name = intent.get("target", "").strip()
        inventory = self.world.get("characters.player.inventory", [])
        weapon = next((i for i in inventory if i.get("equipped") and i["name"].lower() == intent.get("weapon_name", "").lower()), None)
        if not weapon: weapon = next((i for i in inventory if i.get("equipped") and i.get("type") == "weapon"), None)
        if not weapon: return {"allowed": False, "reason": "Нет оружия для атаки."}
        
        dmg_val = weapon.get("damage", 5)
        if isinstance(dmg_val, int):
            dmg_roll = random.randint(1, dmg_val) + self.world.get("characters.player.stats.strength", 10)//5
            dmg_comment = f"1d{dmg_val}+STR"
        else:
            dmg_roll, dmg_comment, _ = calculate_damage(str(dmg_val), self.world.get("characters.player.stats", {}))
            
        target_enemy = next((e for e in self.world.get("enemies", []) if e["name"].lower() == target_name.lower()), None)
        updates = []
        ctx = {"attack": True, "target": target_name, "weapon": weapon["name"], "damage_dealt": dmg_roll}
        
        combat_feedback = {"damage_dealt": dmg_roll, "mp_spent": 0, "enemy_reaction": None, "target_name": target_name}
        
        if target_enemy:
            new_hp = max(0, target_enemy["health"] - dmg_roll)
            idx = self.world.get("enemies", []).index(target_enemy)
            updates.append({"key": f"enemies.{idx}.health", "value": new_hp})
            ctx["target_health_after"] = new_hp
            combat_feedback["target_health_after"] = new_hp
            if new_hp <= 0:
                ctx["target_died"] = True
                combat_feedback["enemy_reaction"] = "defeated"
            else:
                combat_feedback["enemy_reaction"] = "staggered" if dmg_roll >= target_enemy.get("max_health", 25) * 0.3 else "normal"

        return {
            "allowed": True, "updates": updates, "memory": [],
            "narrator_context": ctx, "system_message": f"⚔️ Атака {weapon['name']}",
            "combat_feedback": combat_feedback
        }

    def _handle_interact(self, intent: dict) -> dict:
        return {"allowed": True, "updates": [], "memory": [f"Осмотр {intent.get('object', '')}"], "narrator_context": {"interact": True}}
    def _handle_move(self, intent: dict) -> dict:
        return {"allowed": True, "updates": [{"key": "location", "value": f"{self.world.get('location')} - {intent.get('direction', '')}"}], "memory": [], "narrator_context": {"move": True}}
    def _handle_talk(self, intent: dict) -> dict:
        return {"allowed": True, "updates": [], "memory": [], "narrator_context": {"talk": True}}
    def _handle_generic(self, intent: dict) -> dict:
        return {"allowed": True, "updates": [], "memory": [], "narrator_context": {"generic": intent.get("description", "")}}

class StateApplier:
    def __init__(self, world: WorldState):
        self.world = world
        self._backup = None
    def begin_transaction(self):
        self._backup = copy.deepcopy(self.world.state)
    def commit(self):
        self._backup = None
        self.world._save()
    def rollback(self):
        if self._backup:
            self.world.state = self._backup
            self.world._save()
        self._backup = None
    def bulk_update(self, updates_dict: Dict[str, Any]):
        for k, v in updates_dict.items():
            self.world.update(k, v)