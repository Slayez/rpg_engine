# backend/engine/narrative_engine.py

import json, copy, logging, asyncio
from world_state import WorldState
from memory import LongTermMemory
from llm_client import LLMClient
from .action_resolver import IntentParser, ActionExecutor, StateApplier
from .narration import NarrationGenerator

logger = logging.getLogger(__name__)

class NarrativeEngine:
    def __init__(self, world: WorldState, memory: LongTermMemory):
        self.world = world
        self.memory = memory
        self.llm = LLMClient()
        # Разделение ответственности
        self.intent_parser = IntentParser(world, self.llm)
        self.action_executor = ActionExecutor(world)
        self.state_applier = StateApplier(world)
        self.narrator = NarrationGenerator(self)
        self.history = []
        self.action_stack = []
        chat_history = world.get("chat_history", [])
        for msg in chat_history:
            role = msg.get("sender", "assistant")
            self.history.append({"role": role, "content": msg.get("text", "")})
        if len(self.history) > 20:
            self.history = self.history[-20:]

    def add_to_history(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        if len(self.history) > 20:
            self.history = self.history[-20:]

    def _save_checkpoint(self):
        prev_state = copy.deepcopy(self.world.state)
        self.action_stack.append({
            'prev_state': prev_state,
            'history_len': len(self.history),
            'memory_ids': []
        })

    def _build_system_messages(self, old_state, new_state, env_msgs, skill_msgs=None):
        """
        Все параметры – списки словарей вида {"text": ..., "type": ...}.
        skill_msgs – сообщения о применённых навыках (могут быть пустым списком).
        env_msgs – сообщения об уроне окружению.
        """
        msgs = []
        old_p = old_state.get("characters", {}).get("player", {})
        new_p = new_state.get("characters", {}).get("player", {})
        # HP/MP
        for (old_val, new_val, label, type_key) in [
            (old_p.get("health",0), new_p.get("health",0), "❤️ HP", "hp"),
            (old_p.get("mp",0), new_p.get("mp",0), "💙 MP", "mp"),
        ]:
            diff = new_val - old_val
            if diff != 0:
                msgs.append({"text": f"{label} {'+' + str(diff) if diff>0 else diff}", "type": f"{type_key}-{'heal' if diff>0 else 'damage'}"})
        # Опыт
        old_exp = old_p.get("stats", {}).get("exp", 0)
        new_exp = new_p.get("stats", {}).get("exp", 0)
        if new_exp > old_exp:
            msgs.append({"text": f"✨ +{new_exp - old_exp} опыта", "type": "exp-gain"})
        # Уровень
        old_lvl = old_p.get("stats", {}).get("level", 1)
        new_lvl = new_p.get("stats", {}).get("level", 1)
        if new_lvl > old_lvl:
            msgs.append({"text": f"⭐ Уровень повышен до {new_lvl}!", "type": "level-up"})
        # Инвентарь
        old_inv_names = {i["name"] for i in old_p.get("inventory", [])}
        new_inv_names = {i["name"] for i in new_p.get("inventory", [])}
        for item in new_p.get("inventory", []):
            if item["name"] not in old_inv_names:
                msgs.append({"text": f"🆕 Получен предмет: «{item['name']}»", "type": "item-appear"})
        for item in old_p.get("inventory", []):
            if item["name"] not in new_inv_names:
                msgs.append({"text": f"❌ Утерян предмет: «{item['name']}»", "type": "item-removed"})
        # Сначала навыки, затем ресурсы, затем окружение
        if skill_msgs:
            msgs = skill_msgs + msgs
        msgs.extend(env_msgs)
        return msgs

    async def stream_process_action(self, player_action: str):
        old_state = copy.deepcopy(self.world.state)
        
        # 1. Парсинг интентов (IntentParser)
        intents = await self.intent_parser.extract_intents(player_action)
        if not intents:
            intents = [{"action_type": "other", "description": player_action}]
        
        # 2. Выполнение всех интентов и сбор изменений (ActionExecutor)
        combined = {
            "allowed": True,
            "updates": [],
            "memory": [],
            "narrator_contexts": [],
            "system_messages": [],
        }
        
        for intent in intents:
            action_type = intent.get("action_type")
            if action_type == "repeat_skill":
                result = await self.action_executor._handle_repeat_skill(intent)
            elif action_type == "use_skill":
                result = self.action_executor._handle_skill(intent)
            elif action_type == "attack":
                result = self.action_executor._handle_attack(intent)
            elif action_type == "interact":
                result = self.action_executor._handle_interact(intent)
            elif action_type == "move":
                result = self.action_executor._handle_move(intent)
            elif action_type == "talk":
                result = self.action_executor._handle_talk(intent)
            else:
                result = self.action_executor._handle_generic(intent)

            if not result["allowed"]:
                error_msg = result["reason"]
                self.add_to_history("user", player_action)
                self.add_to_history("assistant", error_msg)
                self._save_chat_history()
                yield f"data: {json.dumps({'type':'done','narration':error_msg,'world_state':self.world.snapshot()})}\n\n"
                return

            combined["updates"].extend(result.get("updates", []))
            combined["memory"].extend(result.get("memory", []))
            if "narrator_context" in result:
                combined["narrator_contexts"].append(result["narrator_context"])
            if "system_message" in result:
                combined["system_messages"].append(result["system_message"])
            # Собираем combat_feedback от каждого интента
            if "combat_feedback" in result:
                if "combat_feedback_list" not in combined:
                    combined["combat_feedback_list"] = []
                combined["combat_feedback_list"].append(result["combat_feedback"])
        
        result = combined
        self._save_checkpoint()

        # 3. Атомарное применение изменений (StateApplier)
        self.state_applier.begin_transaction()
        try:
            updates_dict = {}
            for upd in result.get("updates", []):
                updates_dict[upd["key"]] = upd["value"]
            self.state_applier.bulk_update(updates_dict)
            self.state_applier.commit()
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            self.state_applier.rollback()
            error_msg = f"Ошибка применения изменений: {str(e)}"
            self.add_to_history("user", player_action)
            self.add_to_history("assistant", error_msg)
            self._save_chat_history()
            yield f"data: {json.dumps({'type':'done','narration':error_msg,'world_state':self.world.snapshot()})}\n\n"
            return

        mem_ids = []
        for mem_text in result.get("memory", []):
            mid = self.memory.add_memory(mem_text)
            mem_ids.append(mid)
        self.action_stack[-1]['memory_ids'] = mem_ids

        self.world.apply_passive_regen()
        self.world.reduce_cooldowns()
        self.world.enforce_resource_limits()

        # Собираем combat_feedback из всех интентов
        combat_feedback_list = result.get("combat_feedback_list", [])
        
        skill_msgs_str = result.get("system_messages", [])
        skill_msgs = [{"text": msg, "type": "skill_use"} for msg in skill_msgs_str]
        
        # Добавляем сообщения о боевом фидбеке
        fb_msgs = []
        for fb in combat_feedback_list:
            if fb.get("damage_dealt") and fb.get("damage_dealt") > 0:
                fb_msgs.append({"text": f"⚔️ Нанесено {fb['damage_dealt']} урона", "type": "enemy-damage"})
            if fb.get("mp_spent") and fb.get("mp_spent") > 0:
                fb_msgs.append({"text": f"💙 -{fb['mp_spent']} MP", "type": "mp-spent"})
            if fb.get("enemy_reaction") == "staggered":
                fb_msgs.append({"text": f"🐺 {fb.get('target_name', 'Враг')} отшатнулся!", "type": "enemy-reaction"})
            elif fb.get("enemy_reaction") == "defeated":
                fb_msgs.append({"text": f"💀 {fb.get('target_name', 'Враг')} повержен!", "type": "enemy-defeated"})
        
        env_msgs = []
        system_messages = self._build_system_messages(old_state, self.world.state, env_msgs, skill_msgs + fb_msgs)

        # Генерируем нарратив
        narration = await self.narrator.generate_from_result(player_action, result.get("narrator_contexts", []))

        self.add_to_history("user", player_action)
        for sm in system_messages:
            self.add_to_history("system", sm["text"])
        self.add_to_history("assistant", narration)
        
        # Обработка хода врагов (ИИ-реакция)
        enemy_actions = await self._process_enemy_turn()
        if enemy_actions:
            for action in enemy_actions:
                enemy_msg = {"text": action["description"], "type": "enemy-action"}
                system_messages.append(enemy_msg)
                self.add_to_history("system", action["description"])
                
                # Применяем эффекты действий врагов
                if action.get("damage_to_player"):
                    current_hp = self.world.get("characters.player.health", 100)
                    new_hp = max(0, current_hp - action["damage_to_player"])
                    self.world.update("characters.player.health", new_hp)
                    system_messages.append({
                        "text": f"💔 Вы получили {action['damage_to_player']} урона",
                        "type": "hp-damage"
                    })
        
        self._save_chat_history()

        # Стриминг нарратива
        for i in range(0, len(narration), 50):
            yield f"data: {json.dumps({'type':'text','content':narration[i:i+50]})}\n\n"
            await asyncio.sleep(0.01)

        # Отправляем системные сообщения (включая действия врагов)
        for sm in system_messages:
            yield f"data: {json.dumps({'type':'system_message','text':sm['text'],'msg_type':sm['type']})}\n\n"

        # Обновляем world_state после действий врагов
        final = json.dumps({
            "type": "done",
            "narration": narration,
            "world_state": self.world.snapshot(),
            "system_messages": system_messages
        }, ensure_ascii=False)
        yield f"data: {final}\n\n"

    def _save_chat_history(self):
        msgs = [{"sender": m["role"], "text": m["content"]} for m in self.history]
        self.world.update("chat_history", msgs)

    async def process_action(self, player_action: str):
        """Нестримовая версия (используется для undo/retry/edit). Возвращает (narration, system_messages)."""
        old_state = copy.deepcopy(self.world.state)
        
        # 1. Парсинг интентов (IntentParser)
        intents = await self.intent_parser.extract_intents(player_action)
        if not intents:
            intents = [{"action_type": "other", "description": player_action}]
        
        # 2. Выполнение всех интентов и сбор изменений (ActionExecutor)
        combined = {
            "allowed": True,
            "updates": [],
            "memory": [],
            "narrator_contexts": [],
            "system_messages": [],
        }
        
        for intent in intents:
            action_type = intent.get("action_type")
            if action_type == "repeat_skill":
                result = await self.action_executor._handle_repeat_skill(intent)
            elif action_type == "use_skill":
                result = self.action_executor._handle_skill(intent)
            elif action_type == "attack":
                result = self.action_executor._handle_attack(intent)
            elif action_type == "interact":
                result = self.action_executor._handle_interact(intent)
            elif action_type == "move":
                result = self.action_executor._handle_move(intent)
            elif action_type == "talk":
                result = self.action_executor._handle_talk(intent)
            else:
                result = self.action_executor._handle_generic(intent)

            if not result["allowed"]:
                return result["reason"], []

            combined["updates"].extend(result.get("updates", []))
            combined["memory"].extend(result.get("memory", []))
            if "narrator_context" in result:
                combined["narrator_contexts"].append(result["narrator_context"])
            if "system_message" in result:
                combined["system_messages"].append(result["system_message"])
            # Собираем combat_feedback от каждого интента
            if "combat_feedback" in result:
                if "combat_feedback_list" not in combined:
                    combined["combat_feedback_list"] = []
                combined["combat_feedback_list"].append(result["combat_feedback"])
        
        result = combined
        self._save_checkpoint()

        # 3. Атомарное применение изменений (StateApplier)
        self.state_applier.begin_transaction()
        try:
            updates_dict = {}
            for upd in result.get("updates", []):
                updates_dict[upd["key"]] = upd["value"]
            self.state_applier.bulk_update(updates_dict)
            self.state_applier.commit()
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            self.state_applier.rollback()
            return f"Ошибка применения изменений: {str(e)}", []

        for mem_text in result.get("memory", []):
            self.memory.add_memory(mem_text)
        self.world.apply_passive_regen()
        self.world.reduce_cooldowns()
        self.world.enforce_resource_limits()

        skill_msgs_str = result.get("system_messages", [])
        skill_msgs = [{"text": msg, "type": "skill_use"} for msg in skill_msgs_str]
        env_msgs = []
        system_messages = self._build_system_messages(old_state, self.world.state, env_msgs, skill_msgs)

        narration = await self.narrator.generate_from_result(player_action, result.get("narrator_contexts", []))
        self.add_to_history("user", player_action)
        for sm in system_messages:
            self.add_to_history("system", sm["text"])
        self.add_to_history("assistant", narration)
        self._save_chat_history()
        return narration, system_messages

    def undo_last_action(self):
        if not self.action_stack:
            raise ValueError("Нет действий для отката")
        if len(self.history) < 2:
            raise ValueError("Нельзя удалить стартовое сообщение")
        checkpoint = self.action_stack.pop()
        self.world.state = checkpoint['prev_state']
        self.world._save()
        if checkpoint.get('memory_ids'):
            self.memory.delete_memories(checkpoint['memory_ids'])
        self.history = self.history[:checkpoint['history_len']]
        self._save_chat_history()

    async def retry_last_action(self):
        if len(self.history) < 2:
            raise ValueError("Нет последнего ответа для перегенерации")
        last_user_msg = next((m['content'] for m in reversed(self.history) if m['role']=='user'), None)
        if not last_user_msg:
            raise ValueError("Не найдено сообщение пользователя")
        self.undo_last_action()
        return await self.process_action(last_user_msg)

    async def edit_last_user_message(self, new_action: str):
        if len(self.history) < 2:
            raise ValueError("Нечего редактировать")
        self.undo_last_action()
        return await self.process_action(new_action)

    async def _process_enemy_turn(self):
        """Генерация ответа врагов через простые правила + LLM."""
        enemies = self.world.get("enemies", [])
        if not enemies:
            return []
        
        player_stats = self.world.get("characters.player.stats", {})
        player_hp = self.world.get("characters.player.health", 100)
        location = self.world.get("location", "Неизвестно")
        
        actions = []
        for enemy in enemies:
            if enemy.get("health", 0) <= 0:
                continue
            
            enemy_hp = enemy.get("health", 25)
            enemy_max_hp = enemy.get("max_health", 25)
            hp_percent = enemy_hp / enemy_max_hp if enemy_max_hp > 0 else 1
            
            # Простые правила ИИ
            action = None
            if hp_percent < 0.3:
                # Враг ранен - может отступить или атаковать в отчаянии
                import random
                if random.random() < 0.5:
                    action = {
                        "enemy_id": enemy.get("id"),
                        "action": "flee",
                        "description": f"🐺 {enemy['name']} отступает с поджатым хвостом!",
                        "damage_to_player": 0
                    }
                else:
                    dmg = enemy.get("damage", 5)
                    action = {
                        "enemy_id": enemy.get("id"),
                        "action": "attack_desperate",
                        "description": f"🐺 {enemy['name']} в отчаянии контратакует и наносит {dmg} урона!",
                        "damage_to_player": dmg
                    }
            elif hp_percent < 0.6:
                # Враг ранен - атакует
                dmg = enemy.get("damage", 5)
                action = {
                    "enemy_id": enemy.get("id"),
                    "action": "attack",
                    "description": f"🐺 {enemy['name']} рычит и атакует, нанося {dmg} урона!",
                    "damage_to_player": dmg
                }
            else:
                # Враг здоров - может атаковать или занять позицию
                import random
                if random.random() < 0.7:
                    dmg = enemy.get("damage", 5)
                    action = {
                        "enemy_id": enemy.get("id"),
                        "action": "attack",
                        "description": f"🐺 {enemy['name']} нападает и наносит {dmg} урона!",
                        "damage_to_player": dmg
                    }
                else:
                    action = {
                        "enemy_id": enemy.get("id"),
                        "action": "taunt",
                        "description": f"🐺 {enemy['name']} угрожающе рычит, готовясь к бою!",
                        "damage_to_player": 0
                    }
            
            if action:
                actions.append(action)
        
        return actions