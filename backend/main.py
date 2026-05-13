# backend/main.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models import *
from game_manager import GameManager
import config
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Narrative Engine RPG")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

manager = GameManager()

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске приложения."""
    os.makedirs(config.SAVES_DIR, exist_ok=True)
    logger.info(f"Saves directory: {os.path.abspath(config.SAVES_DIR)}")

@app.get("/saves", response_model=List[WorldListItem])
def list_saves():
    try:
        return manager.list_saves()
    except Exception as e:
        logger.error(f"Error listing saves: {e}")
        return []

@app.post("/saves", response_model=dict)
def create_world(req: CreateWorldRequest):
    if not req.name.strip():
        raise HTTPException(400, "Имя не может быть пустым")
    race = next((r for r in AVAILABLE_RACES if r.id == req.race_id), None)
    if not race:
        raise HTTPException(400, "Неизвестная раса")
    slot_id = manager.create_world(req.name.strip(), req.race_id)
    return {"slot_id": slot_id}

@app.post("/generate-start-skills", response_model=GenerateSkillsResponse)
async def generate_start_skills(req: GenerateSkillsRequest):
    skills = await manager.generate_start_skills(req.name, req.race_id)
    return {"skills": skills}

# backend/main.py (замените существующий роут choose_start_skills)

from typing import Dict, Any

@app.post("/choose-start-skills", response_model=dict)
def choose_start_skills(req: Dict[str, Any]):
    skills = req.get("skills", [])
    slot_id = req.get("slot_id")
    
    if not slot_id:
        raise HTTPException(400, "slot_id обязателен")
        
    expected_count = config.START_SKILLS_CHOICE_COUNT
    if len(skills) != expected_count:
        logger.warning(f"Неверное количество навыков: ожидалось {expected_count}, получено {len(skills)}")
        raise HTTPException(400, f"Необходимо выбрать ровно {expected_count} навыков (получено: {len(skills)})")
        
    # Передаём навыки напрямую как список dict, без model_dump()
    manager.choose_start_skills(slot_id, skills)
    return {"status": "ok"}

from fastapi.responses import StreamingResponse

@app.post("/action/stream")
async def stream_action(req: SlotActionRequest):
    try:
        engine = manager.load_engine(req.slot_id)
    except FileNotFoundError:
        raise HTTPException(404, "Мир не найден")
    async def event_stream():
        async for chunk in engine.stream_process_action(req.action):
            yield chunk
    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/world")
def get_world(slot_id: str):
    try:
        engine = manager.load_engine(slot_id)
        snapshot = engine.world.snapshot()
        chat = snapshot.get("chat_history", [])
        narration = chat[-1]['text'] if chat else "Мир пуст."
        return GameResponse(narration=narration, world_state=snapshot, chat_history=chat)
    except FileNotFoundError:
        raise HTTPException(404, "Мир не найден")

@app.delete("/saves/{slot_id}")
def delete_save(slot_id: str):
    manager.delete_save(slot_id)
    return {"status": "ok"}

@app.post("/action/undo")
def undo_action(req: SlotActionRequest):
    try:
        engine = manager.load_engine(req.slot_id)
        engine.undo_last_action()
        return GameResponse(narration="Последнее действие отменено.", world_state=engine.world.snapshot())
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(404, "Мир не найден")

@app.post("/action/retry")
async def retry_action(req: SlotActionRequest):
    try:
        engine = manager.load_engine(req.slot_id)
        narration = await engine.retry_last_action()
        return GameResponse(narration=narration, world_state=engine.world.snapshot())
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(404, "Мир не найден")

@app.post("/action/edit")
async def edit_action(req: SlotActionRequest):
    try:
        engine = manager.load_engine(req.slot_id)
        narration = await engine.edit_last_user_message(req.action)
        return GameResponse(narration=narration, world_state=engine.world.snapshot())
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(404, "Мир не найден")

@app.get("/memory")
def get_memory(slot_id: str, n_results: int = 10):
    try:
        engine = manager.load_engine(slot_id)
    except FileNotFoundError:
        raise HTTPException(404, "Мир не найден")
    try:
        memories = engine.memory.get_recent(n_results)
        return {"memories": memories}
    except Exception as e:
        logger.error(f"Memory fetch error: {e}")
        return {"memories": [], "error": "Сервис памяти временно недоступен"}

@app.post("/scene/move")
def scene_move(req: SceneMoveRequest):
    """Перемещение игрока в сцене"""
    try:
        engine = manager.load_engine(req.slot_id)
        success = engine.world.move_player_to(req.x, req.y)
        return {"success": success}
    except FileNotFoundError:
        raise HTTPException(404, "Мир не найден")
    except Exception as e:
        logger.error(f"Scene move error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/scene/interact")
def scene_interact(req: SceneInteractRequest):
    """Взаимодействие с объектом сцены"""
    try:
        engine = manager.load_engine(req.slot_id)
        result = engine.world.interact_with_object(req.object_id, req.action)
        return result
    except FileNotFoundError:
        raise HTTPException(404, "Мир не найден")
    except Exception as e:
        logger.error(f"Scene interact error: {e}")
        return {"success": False, "error": str(e)}

@app.get("/scene")
def get_scene(slot_id: str):
    """Получение текущей сцены"""
    try:
        engine = manager.load_engine(slot_id)
        scene_data = engine.world.generate_scene_from_location()
        return scene_data
    except FileNotFoundError:
        raise HTTPException(404, "Мир не найден")
    except Exception as e:
        logger.error(f"Get scene error: {e}")
        return {"scene": None, "error": str(e)}

@app.get("/config", response_model=dict)
def get_game_config():
    """Получение конфигурации игры"""
    return {
        "start_skills_count": config.START_SKILLS_CHOICE_COUNT
    }

# ========== API для тактического боя ==========

@app.post("/combat/tactical/start")
def start_tactical_combat(req: dict):
    """Начало тактического боя"""
    try:
        engine = manager.load_engine(req.get("slot_id"))
        units = req.get("units", [])
        # Инициализация боя
        engine.world.update("combat_state", {
            "active": True,
            "type": "tactical",
            "units": units,
            "turn": 1,
            "current_turn_unit": units[0]["id"] if units else None
        })
        return {"success": True, "combat_state": engine.world.get("combat_state")}
    except FileNotFoundError:
        raise HTTPException(404, "Мир не найден")
    except Exception as e:
        logger.error(f"Start tactical combat error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/combat/tactical/move")
def tactical_move(req: dict):
    """Перемещение юнита в тактическом бою"""
    try:
        engine = manager.load_engine(req.get("slot_id"))
        unit_id = req.get("unit_id")
        x, y = req.get("x"), req.get("y")
        
        combat_state = engine.world.get("combat_state", {})
        units = combat_state.get("units", [])
        
        # Найти и переместить юнита
        for i, unit in enumerate(units):
            if unit.get("id") == unit_id:
                units[i]["x"] = x
                units[i]["y"] = y
                break
        
        engine.world.update("combat_state.units", units)
        return {"success": True, "combat_state": engine.world.get("combat_state")}
    except FileNotFoundError:
        raise HTTPException(404, "Мир не найден")
    except Exception as e:
        logger.error(f"Tactical move error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/combat/tactical/attack")
def tactical_attack(req: dict):
    """Атака в тактическом бою"""
    try:
        engine = manager.load_engine(req.get("slot_id"))
        attacker_id = req.get("attacker_id")
        target_id = req.get("target_id")
        
        combat_state = engine.world.get("combat_state", {})
        units = combat_state.get("units", [])
        
        attacker = next((u for u in units if u.get("id") == attacker_id), None)
        target = next((u for u in units if u.get("id") == target_id), None)
        
        if not attacker or not target:
            return {"success": False, "error": "Юнит не найден"}
        
        # Расчет урона
        damage = attacker.get("damage", 5)
        target["health"] = max(0, target.get("health", 0) - damage)
        
        result = {
            "success": True,
            "damage": damage,
            "target_health": target["health"],
            "target_defeated": target["health"] <= 0
        }
        
        engine.world.update("combat_state.units", units)
        return {**result, "combat_state": engine.world.get("combat_state")}
    except FileNotFoundError:
        raise HTTPException(404, "Мир не найден")
    except Exception as e:
        logger.error(f"Tactical attack error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/combat/tactical/skill")
def tactical_skill(req: dict):
    """Использование навыка в тактическом бою"""
    try:
        engine = manager.load_engine(req.get("slot_id"))
        unit_id = req.get("unit_id")
        skill_name = req.get("skill_name")
        target_x, target_y = req.get("target_x"), req.get("target_y")
        
        combat_state = engine.world.get("combat_state", {})
        units = combat_state.get("units", [])
        
        unit = next((u for u in units if u.get("id") == unit_id), None)
        if not unit:
            return {"success": False, "error": "Юнит не найден"}
        
        # Проверка MP
        if unit.get("mp", 0) < (unit.get("skill_cost", 0) or 0):
            return {"success": False, "error": "Недостаточно MP"}
        
        result = {
            "success": True,
            "skill_used": skill_name,
            "target_position": {"x": target_x, "y": target_y}
        }
        
        engine.world.update("combat_state.units", units)
        return {**result, "combat_state": engine.world.get("combat_state")}
    except FileNotFoundError:
        raise HTTPException(404, "Мир не найден")
    except Exception as e:
        logger.error(f"Tactical skill error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/combat/tactical/end-turn")
def end_tactical_turn(req: dict):
    """Завершение хода в тактическом бою"""
    try:
        engine = manager.load_engine(req.get("slot_id"))
        
        combat_state = engine.world.get("combat_state", {})
        units = combat_state.get("units", [])
        current_turn = combat_state.get("turn", 1)
        
        # Найти следующего юнита по инициативе
        sorted_units = sorted(units, key=lambda u: u.get("initiative", 0), reverse=True)
        current_idx = next((i for i, u in enumerate(sorted_units) if u.get("id") == combat_state.get("current_turn_unit")), -1)
        next_idx = (current_idx + 1) % len(sorted_units)
        
        # Если цикл завершился, увеличить номер хода
        if next_idx <= current_idx and current_idx != -1:
            current_turn += 1
        
        new_current_unit = sorted_units[next_idx]["id"] if sorted_units else None
        
        engine.world.update("combat_state", {
            **combat_state,
            "turn": current_turn,
            "current_turn_unit": new_current_unit
        })
        
        return {
            "success": True,
            "turn": current_turn,
            "current_unit": new_current_unit,
            "combat_state": engine.world.get("combat_state")
        }
    except FileNotFoundError:
        raise HTTPException(404, "Мир не найден")
    except Exception as e:
        logger.error(f"End tactical turn error: {e}")
        return {"success": False, "error": str(e)}
