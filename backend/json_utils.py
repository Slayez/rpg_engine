# backend/json_utils.py
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
        extra = "allow"

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
        return v.lower() if v.lower() in allowed else "none"

def extract_json(text: str) -> dict:
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
    else:
        match = re.search(r'(\{"narration"\s*:.*\})', text, re.DOTALL)
        json_str = match.group(1) if match else re.search(r'\{.*\}', text, re.DOTALL).group() if re.search(r'\{.*\}', text, re.DOTALL) else None
    if not json_str:
        raise ValueError("JSON not found")
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return json.loads(repair_json(json_str))

def parse_intents(raw_data: Any) -> List[Dict[str, Any]]:
    """Парсит сырые данные в список интентов с валидацией через pydantic."""
    # Тихая обработка fallback-сообщения от LLM
    if isinstance(raw_data, str) and "Сервер мыслей перегружен" in raw_data:
        return [{"action_type": "other", "description": "Действие не распознано (LLM временно недоступен)"}]
        
    if not raw_data:
        return [{"action_type": "other", "description": "Пустое действие"}]
        
    if isinstance(raw_data, str):
        try:
            raw_data = json.loads(raw_data)
        except json.JSONDecodeError:
            return [{"action_type": "other", "description": raw_data}]
            
    raw_list = [raw_data] if isinstance(raw_data, dict) else raw_data if isinstance(raw_data, list) else []
    if not raw_list:
        return [{"action_type": "other", "description": str(raw_data)}]
        
    intents = []
    for i, item in enumerate(raw_list):
        if not isinstance(item, dict):
            continue
        action_type = item.get("action_type", "other")
        try:
            if action_type == "use_skill": parsed = UseSkillIntent(**item)
            elif action_type == "attack": parsed = AttackIntent(**item)
            elif action_type == "interact": parsed = InteractIntent(**item)
            elif action_type == "move": parsed = MoveIntent(**item)
            elif action_type == "talk": parsed = TalkIntent(**item)
            elif action_type == "repeat_skill": parsed = RepeatSkillIntent(**item)
            else: parsed = GenericIntent(**item)
            intents.append(parsed.dict())
        except Exception as e:
            intents.append({
                "action_type": action_type if action_type in ["use_skill", "attack", "interact", "move", "talk", "other"] else "other",
                "description": str(item)
            })
    return intents if intents else [{"action_type": "other", "description": "Не распознано"}]

def parse_skills(raw_data: Any) -> List[Dict[str, Any]]:
    if not raw_data: return []
    if isinstance(raw_data, str):
        try: raw_data = json.loads(raw_data)
        except: return []
    raw_list = [raw_data] if isinstance(raw_data, dict) else raw_data if isinstance(raw_data, list) else []
    skills = []
    for item in raw_list:
        if not isinstance(item, dict): continue
        try:
            skills.append(SkillSchema(**item).dict())
        except Exception:
            skills.append({
                "name": item.get("name", "Навык"),
                "category": item.get("category", "Универсальная магия"),
                "description": item.get("description", ""),
                "effect": item.get("effect", ""),
                "cost_mp": int(item.get("cost_mp", 0)),
                "cast_time": float(item.get("cast_time", 0)),
                "cooldown": int(item.get("cooldown", 0)),
                "range": item.get("range", "0 м"),
                "duration": item.get("duration", ""),
                "damage": item.get("damage", "0"),
                "damage_type": item.get("damage_type", "none"),
                "requirements": item.get("requirements", ""),
                "passive": bool(item.get("passive", False))
            })
    return skills