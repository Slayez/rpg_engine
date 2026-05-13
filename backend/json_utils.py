import json
import re
import logging
from typing import Dict, Any, List, Optional, Union
from json_repair import repair_json
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


# === Pydantic схемы для интентов ===
class IntentBase(BaseModel):
    action_type: str
    
    class Config:
        extra = "allow"  # Разрешаем дополнительные поля для гибкости


class UseSkillIntent(IntentBase):
    action_type: str = "use_skill"
    skill_name: str = Field(..., min_length=1)
    target: Optional[str] = ""


class AttackIntent(IntentBase):
    action_type: str = "attack"
    weapon_name: Optional[str] = ""
    target: str = Field(..., min_length=1)


class InteractIntent(IntentBase):
    action_type: str = "interact"
    object: str = Field(..., min_length=1)


class MoveIntent(IntentBase):
    action_type: str = "move"
    direction: str = Field(..., min_length=1)


class TalkIntent(IntentBase):
    action_type: str = "talk"
    target: str = Field(..., min_length=1)


class RepeatSkillIntent(IntentBase):
    action_type: str = "repeat_skill"
    skill_name: str = Field(..., min_length=1)
    target: Optional[str] = ""
    count: int = Field(..., ge=1, le=100)
    wait_cooldown: bool = False


class GenericIntent(IntentBase):
    action_type: str = "other"
    description: str = Field(..., min_length=1)


# Union всех типов интентов для парсинга
IntentSchema = Union[UseSkillIntent, AttackIntent, InteractIntent, MoveIntent, TalkIntent, RepeatSkillIntent, GenericIntent]


# === Pydantic схемы для навыков ===
class SkillSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    category: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1, max_length=200)
    effect: str = Field(..., min_length=1, max_length=100)
    cost_mp: int = Field(..., ge=0, le=1000)
    cast_time: float = Field(..., ge=0, le=60)
    cooldown: int = Field(..., ge=0, le=300)
    range: str = Field(..., max_length=20)
    duration: str = Field(default="", max_length=50)
    damage: str = Field(default="0", max_length=50)
    damage_type: str = Field(default="none", max_length=20)
    requirements: str = Field(default="", max_length=100)
    passive: bool = Field(default=False)
    
    @validator('damage_type')
    def validate_damage_type(cls, v):
        allowed = {"physical", "magical", "fire", "water", "earth", "air", "heal", "none"}
        if v.lower() not in allowed:
            return "none"
        return v.lower()


def extract_json(text: str) -> dict:
    """Извлекает JSON из ответа LLM, пробуя repair_json при ошибке."""
    # 1. Ищем ```json ... ```
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
    else:
        # 2. Ищем JSON-объект, который содержит ключ "narration"
        match = re.search(r'(\{"narration"\s*:.*\})', text, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            # 3. Ищем первую '{' и последнюю '}'
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                json_str = match.group()
            else:
                raise ValueError("JSON not found")
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        try:
            repaired = repair_json(json_str)
            return json.loads(repaired)
        except Exception as e:
            logger.error(f"JSON repair failed: {e}")
            raise ValueError("Broken JSON")


def parse_intents(raw_data: Any) -> List[Dict[str, Any]]:
    """Парсит сырые данные в список интентов с валидацией через pydantic."""
    if not raw_data:
        return [{"action_type": "other", "description": "Пустое действие"}]
    
    intents = []
    
    # Нормализуем входные данные
    if isinstance(raw_data, str):
        try:
            raw_data = json.loads(raw_data)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse raw intent string: {raw_data}")
            return [{"action_type": "other", "description": raw_data}]
    
    # Преобразуем в список
    if isinstance(raw_data, dict):
        raw_list = [raw_data]
    elif isinstance(raw_data, list):
        raw_list = raw_data
    else:
        logger.error(f"Unexpected intent format: {type(raw_data)}")
        return [{"action_type": "other", "description": str(raw_data)}]
    
    # Парсим каждый интент
    for i, item in enumerate(raw_list):
        if not isinstance(item, dict):
            logger.warning(f"Intent {i} is not a dict, skipping")
            continue
        
        action_type = item.get("action_type", "other")
        try:
            if action_type == "use_skill":
                parsed = UseSkillIntent(**item)
            elif action_type == "attack":
                parsed = AttackIntent(**item)
            elif action_type == "interact":
                parsed = InteractIntent(**item)
            elif action_type == "move":
                parsed = MoveIntent(**item)
            elif action_type == "talk":
                parsed = TalkIntent(**item)
            elif action_type == "repeat_skill":
                parsed = RepeatSkillIntent(**item)
            else:
                parsed = GenericIntent(**item)
            
            intents.append(parsed.dict())
        except Exception as e:
            logger.warning(f"Intent {i} validation failed ({action_type}): {e}. Using fallback.")
            # Fallback: создаём минимальный валидный интент
            intents.append({
                "action_type": action_type if action_type in ["use_skill", "attack", "interact", "move", "talk", "other"] else "other",
                "description": str(item)
            })
    
    return intents if intents else [{"action_type": "other", "description": "Не распознано"}]


def parse_skills(raw_data: Any) -> List[Dict[str, Any]]:
    """Парсит сырые данные в список навыков с валидацией через pydantic."""
    if not raw_data:
        return []
    
    skills = []
    
    # Нормализуем входные данные
    if isinstance(raw_data, str):
        try:
            raw_data = json.loads(raw_data)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse raw skill string: {raw_data}")
            return []
    
    # Преобразуем в список
    if isinstance(raw_data, dict):
        raw_list = [raw_data]
    elif isinstance(raw_data, list):
        raw_list = raw_data
    else:
        logger.error(f"Unexpected skill format: {type(raw_data)}")
        return []
    
    # Парсим каждый навык
    for i, item in enumerate(raw_list):
        if not isinstance(item, dict):
            logger.warning(f"Skill {i} is not a dict, skipping")
            continue
        
        try:
            parsed = SkillSchema(**item)
            skills.append(parsed.dict())
        except Exception as e:
            logger.warning(f"Skill {i} validation failed: {e}. Attempting partial parse.")
            # Попытка частичного парсинга с дефолтными значениями
            try:
                partial = {
                    "name": item.get("name", f"Навык_{i}"),
                    "category": item.get("category", "Универсальная магия"),
                    "description": item.get("description", "Описание отсутствует"),
                    "effect": item.get("effect", "Нет эффекта"),
                    "cost_mp": int(item.get("cost_mp", 0)) if item.get("cost_mp") is not None else 0,
                    "cast_time": float(item.get("cast_time", 0)) if item.get("cast_time") is not None else 0,
                    "cooldown": int(item.get("cooldown", 0)) if item.get("cooldown") is not None else 0,
                    "range": item.get("range", "0 м"),
                    "duration": item.get("duration", ""),
                    "damage": item.get("damage", "0"),
                    "damage_type": item.get("damage_type", "none"),
                    "requirements": item.get("requirements", ""),
                    "passive": bool(item.get("passive", False))
                }
                # Валидация damage_type
                allowed_types = {"physical", "magical", "fire", "water", "earth", "air", "heal", "none"}
                if partial["damage_type"].lower() not in allowed_types:
                    partial["damage_type"] = "none"
                skills.append(partial)
            except Exception as e2:
                logger.error(f"Partial parse failed for skill {i}: {e2}")
    
    return skills