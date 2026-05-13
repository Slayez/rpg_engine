# backend/world_state.py

import os, json, copy, time
from typing import Any, Dict, List, Optional
from config import SAVES_DIR
from models import AVAILABLE_RACES

class WorldState:
    def __init__(self, slot_id: str, initial_data: Optional[Dict] = None):
        self.slot_id = slot_id
        self.save_dir = os.path.join(SAVES_DIR, slot_id)
        os.makedirs(self.save_dir, exist_ok=True)
        self.save_file = os.path.join(self.save_dir, "world_state.json")

        loaded = self._load()
        if loaded:
            loaded.setdefault("characters", {}).setdefault("player", {}).setdefault("cooldowns", {})
            loaded.setdefault("environment_objects", {})
            # Инициализация веса и лимитов
            player = loaded.get("characters", {}).get("player", {})
            player.setdefault("carry_capacity", 50)  # Максимальный вес
            for item in player.get("inventory", []):
                item.setdefault("weight", 1.0)
                item.setdefault("stack_size", 1)
            self.state = loaded
        elif initial_data:
            initial_data.setdefault("environment_objects", {})
            player = initial_data.get("characters", {}).get("player", {})
            if player:
                player.setdefault("carry_capacity", 50)
                for item in player.get("inventory", []):
                    item.setdefault("weight", 1.0)
                    item.setdefault("stack_size", 1)
            self.state = initial_data
            self._save()
        else:
            self.state = {}
            self._save()
        
        # Для системы тиков
        self._last_tick = time.time()
        self._tick_interval = 30  # секунд

    def _load(self) -> Optional[Dict]:
        if os.path.exists(self.save_file):
            try:
                with open(self.save_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return None
        return None

    def _save(self):
        with open(self.save_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default=None):
        keys = key.split('.')
        val = self.state
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            elif isinstance(val, list):
                try:
                    idx = int(k)
                    if 0 <= idx < len(val):
                        val = val[idx]
                    else:
                        return default
                except ValueError:
                    return default
            else:
                return default
        return val if val is not None else default

    def update(self, key: str, value: Any):
        keys = key.split('.')
        target = self.state
        for i, k in enumerate(keys[:-1]):
            if isinstance(target, dict):
                if k not in target:
                    target[k] = {} if not isinstance(keys[i+1], int) else []
                target = target[k]
            elif isinstance(target, list):
                try:
                    idx = int(k)
                    if idx >= len(target):
                        target.extend([None] * (idx - len(target) + 1))
                    if target[idx] is None:
                        target[idx] = {} if not isinstance(keys[i+1], int) else []
                    target = target[idx]
                except (ValueError, IndexError):
                    return
            else:
                return
        if isinstance(target, dict):
            target[keys[-1]] = value
        elif isinstance(target, list):
            try:
                idx = int(keys[-1])
                if idx >= len(target):
                    target.extend([None] * (idx - len(target) + 1))
                target[idx] = value
            except ValueError:
                pass
        self._save()

    def snapshot(self) -> Dict:
        return copy.deepcopy(self.state)

    def relevant_snapshot(self, player_action: str) -> Dict:
        base = {
            "location": self.get("location"),
            "time": self.get("time"),
            "player_inventory": self.get("characters.player.inventory"),
            "player_health": self.get("characters.player.health"),
            "player_mp": self.get("characters.player.mp"),
            "player_stats": self.get("characters.player.stats"),
            "player_skills": self.get("characters.player.skills"),
            "player_cooldowns": self.get("characters.player.cooldowns", {}),
            "plot_flags": self.get("plot_flags", {}),
            "enemies": self.get("enemies", []),
            "active_quests": self.get("active_quests", []),
            "environment_objects": self.get("environment_objects", {})
        }
        action_lower = player_action.lower()
        if "дракон" in action_lower or "dragon" in action_lower:
            base["dragon_awake"] = self.get("plot_flags.dragon_awake")
        if "старейшин" in action_lower or "elder" in action_lower:
            base["met_elder"] = self.get("plot_flags.met_elder")
        return base

    def set_initial_skills(self, skills: List[Dict]):
        self.update("characters.player.skills", skills)
        self._save()

    def apply_passive_regen(self):
        player = self.state.setdefault("characters", {}).setdefault("player", {})
        stats = player.get("stats", {})
        hp_max = stats.get("hp", 100)
        mp_max = stats.get("mp", 50)
        hp_regen = stats.get("hp_regen", 1)
        mp_regen = stats.get("mp_regen", 1)
        old_health = player.get("health", hp_max)
        old_mp = player.get("mp", mp_max)
        new_health = min(old_health + hp_regen, hp_max)
        new_mp = min(old_mp + mp_regen, mp_max)
        player["health"] = new_health
        player["mp"] = new_mp
        self._save()

    def reduce_cooldowns(self):
        cooldowns = self.get("characters.player.cooldowns", {})
        if not cooldowns:
            return
        updated = {}
        for skill_name, turns in cooldowns.items():
            new_turns = max(0, turns - 1)
            if new_turns > 0:
                updated[skill_name] = new_turns
        self.update("characters.player.cooldowns", updated)
        self._save()

    def enforce_resource_limits(self):
        player = self.state.get("characters", {}).get("player", {})
        stats = player.get("stats", {})
        hp_max = stats.get("hp", 100)
        mp_max = stats.get("mp", 50)
        if player.get("health", 0) > hp_max:
            self.update("characters.player.health", hp_max)
        if player.get("mp", 0) > mp_max:
            self.update("characters.player.mp", mp_max)

    def check_inventory_weight(self, item_name: str = None, item_weight: float = 0) -> tuple[bool, str]:
        """Проверка лимита веса инвентаря. Возвращает (allowed, error_message)."""
        player = self.state.get("characters", {}).get("player", {})
        inventory = player.get("inventory", [])
        carry_capacity = player.get("carry_capacity", 50)
        
        total_weight = sum(item.get("weight", 1.0) * item.get("stack_size", 1) for item in inventory)
        if item_weight > 0:
            if total_weight + item_weight > carry_capacity:
                return False, f"Перегруз! Вес: {total_weight:.1f}/{carry_capacity} кг"
        return True, ""

    def get_total_inventory_weight(self) -> float:
        """Возвращает общий вес инвентаря."""
        player = self.state.get("characters", {}).get("player", {})
        inventory = player.get("inventory", [])
        return sum(item.get("weight", 1.0) * item.get("stack_size", 1) for item in inventory)

    def process_tick(self):
        """Обработка пассивных эффектов по таймеру (тик каждые 30 сек)."""
        now = time.time()
        if now - self._last_tick >= self._tick_interval:
            self.apply_passive_regen()
            self.reduce_cooldowns()
            self._last_tick = now
            return True
        return False

    @staticmethod
    def default_state(player_name: str, race_id: str) -> Dict:
        race = next((r for r in AVAILABLE_RACES if r.id == race_id), None)
        bonuses = race.bonuses if race else {}
        stats = {
            "level": 1,
            "exp": 0,
            "hp": 100 + bonuses.get("vitality", 0) * 2,
            "mp": 50 + bonuses.get("intelligence", 0) * 2,
            "strength": 10 + bonuses.get("strength", 0),
            "dexterity": 10 + bonuses.get("dexterity", 0),
            "intelligence": 10 + bonuses.get("intelligence", 0),
            "vitality": 10 + bonuses.get("vitality", 0),
            "wisdom": 10 + bonuses.get("wisdom", 0),
            "luck": 10 + bonuses.get("luck", 0),
            "defense": 5 + bonuses.get("defense", 0),
            "magic_defense": 5 + bonuses.get("magic_defense", 0),
            "speed": 10 + bonuses.get("speed", 0),
            "accuracy": 10 + bonuses.get("accuracy", 0),
            "evasion": 5 + bonuses.get("evasion", 0),
            "crit_rate": 5.0,
            "crit_damage": 150.0,
            "hp_regen": 1,
            "mp_regen": 1,
            "charisma": 10 + bonuses.get("charisma", 0)
        }
        inventory = [
            {
                "name": "Ржавый меч",
                "description": "Старый, но ещё острый меч. Наносит 5-7 урона.",
                "type": "weapon",
                "equipped": True,
                "damage": 6,
                "defense": None,
                "stat_bonuses": None,
                "weight": 2.0,
                "stack_size": 1,
                "icon": "⚔️"
            }
        ]
        return {
            "location": "Густой лес",
            "time": "Утро",
            "location_description": "Старый, могучий лес, наполненный магией и тайнами. Кроны деревьев смыкаются высоко над головой, пропуская лишь редкие лучи солнца.",
            "characters": {
                "player": {
                    "name": player_name,
                    "race": race_id,
                    "health": stats["hp"],
                    "mp": stats["mp"],
                    "inventory": inventory,
                    "stats": stats,
                    "skills": [],
                    "cooldowns": {},
                    "carry_capacity": 50
                }
            },
            "enemies": [
                {"id": "wolf_1", "name": "Лесной волк", "health": 25, "max_health": 25, "damage": 6, "type": "beast"}
            ],
            "active_quests": [
                {
                    "id": "q1",
                    "name": "Загадка леса",
                    "description": "Найдите таинственный алтарь в глубине леса.",
                    "objectives": ["Обнаружить алтарь"],
                    "completed": False
                }
            ],
            "plot_flags": {"met_elder": False, "dragon_awake": False},
            "environment_objects": {},
            "chat_history": [
                {"sender": "assistant", "text": "Добро пожаловать в Этерию. Вы находитесь в густом лесу. Утро. Что будете делать?"}
            ]
        }

    def generate_dynamic_quests(self, llm_client) -> list:
        """Генерация динамических квестов при входе в новую локацию."""
        location = self.get("location", "Неизвестно")
        prompt = f"""
Ты — генератор квестов для RPG. Для локации "{location}" создай 1-2 коротких задания.
Верни JSON массив объектов с полями: id, name, description, objectives (массив строк).
Пример: [{{"id": "q_new", "name": "Сбор трав", "description": "Собери 5 лечебных трав", "objectives": ["Найти травы", "Принести алхимику"]}}]
Только JSON, без пояснений.
"""
        import json
        messages = [{"role": "system", "content": prompt}]
        raw = llm_client.completion(messages, max_tokens=256, temperature=0.7, json_mode=True)
        try:
            quests = json.loads(raw)
            if isinstance(quests, list):
                current = self.get("active_quests", [])
                for q in quests:
                    if not any(x.get("id") == q.get("id") for x in current):
                        current.append(q)
                self.update("active_quests", current)
                return quests
        except Exception:
            pass
        return []

    def generate_scene_from_location(self) -> dict:
        """Авто-генерация сцены на основе текущей локации."""
        location = self.get("location", "Неизвестно")
        location_desc = self.get("location_description", "")
        
        # Определение типа локации по названию и описанию
        location_lower = location.lower()
        desc_lower = location_desc.lower()
        
        scene_type = "room"  # по умолчанию
        if any(word in location_lower for word in ["лес", "forest", "поле", "field", "гор", "mountain", "пустош", "waste"]):
            scene_type = "outdoor"
        elif any(word in location_lower for word in ["подземель", "dungeon", "пещер", "cave", "склеп", "crypt"]):
            scene_type = "dungeon"
        
        # Генерация объектов сцены на основе контекста
        objects = []
        
        # Добавляем врагов из world_state
        enemies = self.get("enemies", [])
        for i, enemy in enumerate(enemies):
            enemy_icon = "👹"  # default
            if enemy.get("type") == "beast":
                enemy_icon = "🐺"
            elif enemy.get("type") == "undead":
                enemy_icon = "💀"
            elif enemy.get("type") == "human":
                enemy_icon = "🗡️"
            
            objects.append({
                "id": enemy.get("id", f"enemy_{i}"),
                "type": "enemy",
                "name": enemy.get("name", "Враг"),
                "x": 400 + (i * 80),  # распределение по сцене
                "y": 300 + (i % 3) * 50,
                "icon": enemy_icon,
                "hp": enemy.get("health", 25),
                "max_hp": enemy.get("max_health", 25),
                "damage": enemy.get("damage", 5),
                "interactions": ["attack", "inspect"]
            })
        
        # Добавление интерактивных объектов на основе описания локации
        if "таверн" in location_lower or "tavern" in location_lower:
            objects.append({
                "id": "npc_innkeeper",
                "type": "npc",
                "name": "Трактирщик",
                "x": 500,
                "y": 250,
                "icon": "👨‍🍳",
                "interactions": ["talk", "trade", "rent_room"]
            })
            objects.append({
                "id": "door_exit",
                "type": "door",
                "name": "Выход",
                "x": 400,
                "y": 100,
                "icon": "🚪",
                "interactions": ["leave"]
            })
        
        if "алтар" in location_lower or "altar" in location_lower:
            objects.append({
                "id": "altar",
                "type": "interactive",
                "name": "Древний алтарь",
                "x": 400,
                "y": 200,
                "icon": "🗿",
                "description": "Покрытый рунами алтарь излучает слабое свечение.",
                "interactions": ["pray", "inspect", "offer"]
            })
        
        # Позиция игрока
        player_pos = self.get("player_position", {"x": 200, "y": 300})
        
        return {
            "scene": {
                "type": scene_type,
                "width": 800,
                "height": 600,
                "objects": objects,
                "player": {
                    "x": player_pos.get("x", 200),
                    "y": player_pos.get("y", 300),
                    "icon": "🧙",
                    "facing": player_pos.get("facing", "right")
                }
            }
        }

    def move_player_to(self, x: int, y: int) -> bool:
        """Перемещение игрока в новые координаты."""
        # Проверка границ
        if x < 0 or x > 800 or y < 0 or y > 600:
            return False
        
        self.update("player_position", {"x": x, "y": y, "facing": "right"})
        return True

    def interact_with_object(self, object_id: str, action: str) -> dict:
        """Взаимодействие с объектом сцены."""
        # Поиск объекта в сцене или врагах
        scene_data = self.generate_scene_from_location()
        objects = scene_data.get("scene", {}).get("objects", [])
        
        target_obj = None
        for obj in objects:
            if obj.get("id") == object_id:
                target_obj = obj
                break
        
        if not target_obj:
            return {"success": False, "message": "Объект не найден"}
        
        if action not in target_obj.get("interactions", []):
            return {"success": False, "message": "Недоступное действие"}
        
        # Обработка действий
        result = {
            "success": True,
            "object_id": object_id,
            "action": action,
            "message": f"Вы взаимодействуете с {target_obj['name']}: {action}"
        }
        
        if target_obj["type"] == "enemy" and action == "attack":
            result["combat"] = True
            result["target"] = target_obj
        
        return result