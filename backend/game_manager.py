import json
import os, shutil, uuid, logging
from typing import Dict
from models import Race
from world_state import WorldState
from memory import LongTermMemory
from engine.narrative_engine import NarrativeEngine
from engine.skill_generator import generate_start_skills
from config import SAVES_DIR, CHROMA_PERSIST_DIR

logger = logging.getLogger(__name__)

class GameManager:
    def __init__(self):
        os.makedirs(SAVES_DIR, exist_ok=True)
        self.active_engines: Dict[str, NarrativeEngine] = {}

    def list_saves(self):
        saves = []
        if not os.path.isdir(SAVES_DIR):
            logger.warning(f"Saves directory does not exist: {SAVES_DIR}")
            return saves
        
        try:
            slot_ids = os.listdir(SAVES_DIR)
        except Exception as e:
            logger.error(f"Error listing saves directory: {e}")
            return saves
        
        for slot_id in slot_ids:
            save_file = os.path.join(SAVES_DIR, slot_id, "world_state.json")
            if os.path.isfile(save_file):
                try:
                    with open(save_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    player_data = data.get("characters", {}).get("player", {})
                    stats = player_data.get("stats", {})
                    
                    saves.append({
                        "slot_id": slot_id,
                        "player_name": player_data.get("name", "Неизвестно"),
                        "race": player_data.get("race", "???"),
                        "level": stats.get("level", 1),
                        "location": data.get("location", "???"),
                        "name": f"Мир {slot_id[:6]}"
                    })
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in save file {save_file}: {e}")
                except Exception as e:
                    logger.error(f"Error reading save file {save_file}: {e}")
        
        return saves

    def create_world(self, player_name: str, race_id: str) -> str:
        slot_id = uuid.uuid4().hex[:12]
        initial_state = WorldState.default_state(player_name, race_id)
        world = WorldState(slot_id, initial_state)
        memory = LongTermMemory(slot_id)
        memory.add_memory(f"Персонаж {player_name}, раса {race_id}, начинает приключение.")
        engine = NarrativeEngine(world, memory)
        self.active_engines[slot_id] = engine
        return slot_id

    def load_engine(self, slot_id: str) -> NarrativeEngine:
        if slot_id in self.active_engines:
            return self.active_engines[slot_id]
        save_file = os.path.join(SAVES_DIR, slot_id, "world_state.json")
        if not os.path.isfile(save_file):
            raise FileNotFoundError("Слот не найден")
        world = WorldState(slot_id)
        memory = LongTermMemory(slot_id)
        engine = NarrativeEngine(world, memory)
        self.active_engines[slot_id] = engine
        return engine

    def delete_save(self, slot_id: str):
        # Удаляем движок из памяти (если есть)
        if slot_id in self.active_engines:
            try:
                self.active_engines[slot_id].memory.close()
            except Exception as e:
                logger.warning(f"Memory close failed: {e}")
            del self.active_engines[slot_id]

        # Удаляем файлы сохранения
        save_dir = os.path.join(SAVES_DIR, slot_id)
        if os.path.isdir(save_dir):
            try:
                shutil.rmtree(save_dir)
                logger.info(f"Deleted save directory: {save_dir}")
            except Exception as e:
                logger.error(f"Failed to delete save directory {save_dir}: {e}")

        # Удаляем базу ChromaDB, связанную со слотом
        chroma_dir = os.path.join(CHROMA_PERSIST_DIR, f"slot_{slot_id}")
        if os.path.isdir(chroma_dir):
            try:
                shutil.rmtree(chroma_dir)
                logger.info(f"Deleted chroma directory: {chroma_dir}")
            except Exception as e:
                logger.error(f"Failed to delete chroma directory {chroma_dir}: {e}")

    async def generate_start_skills(self, name: str, race_id: str) -> list:
        return await generate_start_skills(name, race_id)

    def choose_start_skills(self, slot_id: str, skills: list):
        engine = self.load_engine(slot_id)
        engine.world.set_initial_skills(skills)