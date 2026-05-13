# backend/engine/narrative_engine.py

import json, copy, logging, asyncio
from world_state import WorldState
from memory import LongTermMemory
from llm_client import LLMClient
from .action_resolver import ActionResolver
from .narration import NarrationGenerator

logger = logging.getLogger(__name__)

class NarrativeEngine:
    def __init__(self, world: WorldState, memory: LongTermMemory):
        self.world = world
        self.memory = memory
        self.llm = LLMClient()
        self.resolver = ActionResolver(world)
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
        result = await self.resolver.resolve_all(player_action)

        if not result["allowed"]:
            error_msg = result["reason"]
            self.add_to_history("user", player_action)
            self.add_to_history("assistant", error_msg)
            self._save_chat_history()
            yield f"data: {json.dumps({'type':'done','narration':error_msg,'world_state':self.world.snapshot()})}\n\n"
            return

        self._save_checkpoint()

        for upd in result.get("updates", []):
            self.world.update(upd["key"], upd["value"])

        mem_ids = []
        for mem_text in result.get("memory", []):
            mid = self.memory.add_memory(mem_text)
            mem_ids.append(mid)
        self.action_stack[-1]['memory_ids'] = mem_ids

        self.world.apply_passive_regen()
        self.world.reduce_cooldowns()
        self.world.enforce_resource_limits()

        skill_msgs_str = result.get("system_messages", [])   # список строк
        # Преобразуем в список словарей
        skill_msgs = [{"text": msg, "type": "skill_use"} for msg in skill_msgs_str]

        # Сообщения об уроне окружению уже включены в skill_msgs, но для единообразия оставим пустой env_msgs
        env_msgs = []
        system_messages = self._build_system_messages(old_state, self.world.state, env_msgs, skill_msgs)

        # Генерируем нарратив
        narration = await self.narrator.generate_from_result(player_action, result.get("narrator_contexts", []))

        self.add_to_history("user", player_action)
        for sm in system_messages:
            self.add_to_history("system", sm["text"])
        self.add_to_history("assistant", narration)
        self._save_chat_history()

        # Стриминг нарратива
        for i in range(0, len(narration), 50):
            yield f"data: {json.dumps({'type':'text','content':narration[i:i+50]})}\n\n"
            await asyncio.sleep(0.01)

        # Отправляем системные сообщения
        for sm in system_messages:
            yield f"data: {json.dumps({'type':'system_message','text':sm['text'],'msg_type':sm['type']})}\n\n"

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
        result = await self.resolver.resolve_all(player_action)
        if not result["allowed"]:
            return result["reason"], []
        self._save_checkpoint()
        for upd in result.get("updates", []):
            self.world.update(upd["key"], upd["value"])
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