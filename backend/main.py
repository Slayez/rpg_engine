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

@app.post("/choose-start-skills", response_model=dict)
def choose_start_skills(req: ChooseSkillsRequest):
    # Валидация количества выбранных навыков
    if len(req.skills) != config.START_SKILLS_CHOICE_COUNT:
        raise HTTPException(400, f"Необходимо выбрать ровно {config.START_SKILLS_CHOICE_COUNT} навыков")
    manager.choose_start_skills(req.slot_id, [s.model_dump() for s in req.skills])
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