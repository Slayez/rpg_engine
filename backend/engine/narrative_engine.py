# backend/engine/narrative_engine.py
import json, copy, logging, asyncio, random
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
        self.intent_parser = IntentParser(world, self.llm)
        self.action_executor = ActionExecutor(world)
        self.state_applier = StateApplier(world)
        self.narrator = NarrationGenerator(self)
        self.history = []
        self.action_stack = []
        for msg in world.get("chat_history", []):
            self.history.append({"role": msg.get("sender", "assistant"), "content": msg.get("text", "")})
        if len(self.history) > 20: self.history = self.history[-20:]

    def add_to_history(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        if len(self.history) > 20: self.history = self.history[-20:]

    def _save_checkpoint(self):
        self.action_stack.append({'prev_state': copy.deepcopy(self.world.state), 'history_len': len(self.history), 'memory_ids': []})

    def _build_system_messages(self, old_state, new_state, extra_msgs=None):
        msgs = []
        old_p = old_state.get("characters", {}).get("player", {})
        new_p = new_state.get("characters", {}).get("player", {})
        
        for (old_v, new_v, label, t_key) in [
            (old_p.get("health",0), new_p.get("health",0), "❤️ HP", "hp"),
            (old_p.get("mp",0), new_p.get("mp",0), "💙 MP", "mp")
        ]:
            diff = new_v - old_v
            if diff != 0:
                msgs.append({"text": f"{label} {'+' + str(diff) if diff>0 else diff}", "type": f"{t_key}-{'heal' if diff>0 else 'damage'}"})
                
        if extra_msgs:
            msgs = extra_msgs + msgs
        return msgs

    async def stream_process_action(self, player_action: str):
        old_state = copy.deepcopy(self.world.state)
        intents = await self.intent_parser.extract_intents(player_action)
        if not intents: intents = [{"action_type": "other", "description": player_action}]
        
        # ✅ Явная инициализация всех полей
        combined = {
            "allowed": True, "updates": [], "memory": [], "narrator_contexts": [],
            "system_messages": [], "combat_feedback_list": []
        }
        
        for intent in intents:
            result = self.action_executor.execute_intent(intent)
            if not result["allowed"]:
                self.add_to_history("user", player_action)
                self.add_to_history("assistant", result["reason"])
                self._save_chat_history()
                yield f"data: {json.dumps({'type':'done','narration':result['reason'],'world_state':self.world.snapshot()})}\n"
                return
            combined["updates"].extend(result.get("updates", []))
            combined["memory"].extend(result.get("memory", []))
            if "narrator_context" in result: combined["narrator_contexts"].append(result["narrator_context"])
            if "system_message" in result: combined["system_messages"].append(result["system_message"])
            if "combat_feedback" in result: combined["combat_feedback_list"].append(result["combat_feedback"])
            
        result = combined
        self._save_checkpoint()
        
        self.state_applier.begin_transaction()
        try:
            self.state_applier.bulk_update({u["key"]: u["value"] for u in result.get("updates", [])})
            self.state_applier.commit()
        except Exception as e:
            self.state_applier.rollback()
            yield f"data: {json.dumps({'type':'done','narration':f'Ошибка: {e}','world_state':self.world.snapshot()})}\n"
            return
            
        for mem in result.get("memory", []): self.memory.add_memory(mem)
        self.world.apply_passive_regen()
        self.world.reduce_cooldowns()
        self.world.enforce_resource_limits()
        
        # Сбор боевых сообщений
        extra_msgs = []
        for fb in result.get("combat_feedback_list", []):
            if fb.get("damage_dealt", 0) > 0:
                extra_msgs.append({"text": f"⚔️ Нанесено {fb['damage_dealt']} урона", "type": "enemy-damage"})
            if fb.get("mp_spent", 0) > 0:
                extra_msgs.append({"text": f"💙 -{fb['mp_spent']} MP", "type": "mp-spent"})
            if fb.get("target_health_after") is not None:
                extra_msgs.append({"text": f"🐺 {fb.get('target_name', 'Враг')}: {fb['target_health_after']} HP", "type": "enemy-hp"})
            if fb.get("heal_amount", 0) > 0:
                extra_msgs.append({"text": f"💚 Восстановлено {fb['heal_amount']} HP", "type": "hp-heal"})
            if fb.get("enemy_reaction") == "staggered":
                extra_msgs.append({"text": f"🐺 {fb.get('target_name', 'Враг')} отшатнулся!", "type": "enemy-reaction"})
            elif fb.get("enemy_reaction") == "defeated":
                extra_msgs.append({"text": f"💀 {fb.get('target_name', 'Враг')} повержен!", "type": "enemy-defeated"})
                
        system_messages = self._build_system_messages(old_state, self.world.state, extra_msgs)
        narration = await self.narrator.generate_from_result(player_action, result.get("narrator_contexts", []))
        
        self.add_to_history("user", player_action)
        for sm in system_messages: self.add_to_history("system", sm["text"])
        self.add_to_history("assistant", narration)
        
        # Ход врагов (только в бою или с малым шансом)
        primary_action = intents[0].get("action_type", "other") if intents else "other"
        enemy_actions = await self._process_enemy_turn(primary_action)
        for action in enemy_actions:
            system_messages.append({"text": action["description"], "type": "enemy-action"})
            self.add_to_history("system", action["description"])
            if action.get("damage_to_player"):
                cur_hp = self.world.get("characters.player.health", 100)
                new_hp = max(0, cur_hp - action["damage_to_player"])
                self.world.update("characters.player.health", new_hp)
                system_messages.append({"text": f"💔 Вы получили {action['damage_to_player']} урона", "type": "hp-damage"})
                
        self._save_chat_history()
        
        # Стриминг
        for i in range(0, len(narration), 50):
            yield f"data: {json.dumps({'type':'text','content':narration[i:i+50]})}\n"
            await asyncio.sleep(0.01)
        for sm in system_messages:
            yield f"data: {json.dumps({'type':'system_message','text':sm['text'],'msg_type':sm['type']})}\n"
        yield f"data: {json.dumps({'type':'done','narration':narration,'world_state':self.world.snapshot(),'system_messages':system_messages}, ensure_ascii=False)}\n"

    def _save_chat_history(self):
        self.world.update("chat_history", [{"sender": m["role"], "text": m["content"]} for m in self.history])

    async def _process_enemy_turn(self, player_action_type: str = "other"):
        enemies = self.world.get("enemies", [])
        if not enemies: return []
        actions = []
        is_combat = player_action_type in ["attack", "use_skill"]
        
        for enemy in enemies:
            if enemy.get("health", 0) <= 0: continue
            hp_pct = enemy.get("health", 1) / max(1, enemy.get("max_health", 1))
            # Шанс атаки зависит от контекста
            attack_chance = (0.6 if hp_pct < 0.5 else 0.3) if is_combat else 0.05
            
            if random.random() < attack_chance:
                actions.append({
                    "enemy_id": enemy.get("id"), "action": "attack",
                    "description": f"🐺 {enemy['name']} нападает и наносит {enemy.get('damage', 5)} урона!",
                    "damage_to_player": enemy.get("damage", 5)
                })
            elif is_combat and random.random() < 0.2:
                actions.append({
                    "enemy_id": enemy.get("id"), "action": "taunt",
                    "description": f"🐺 {enemy['name']} угрожающе рычит!",
                    "damage_to_player": 0
                })
        return actions

    def undo_last_action(self):
        if not self.action_stack: raise ValueError("Нет действий для отката")
        cp = self.action_stack.pop()
        self.world.state = cp['prev_state']
        self.world._save()
        self.history = self.history[:cp['history_len']]
        self._save_chat_history()