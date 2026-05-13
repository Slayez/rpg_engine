# backend/models.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# ---------- Базовые игровые модели ----------
class Race(BaseModel):
    id: str
    name: str
    description: str
    bonuses: Dict[str, int]
    physical_traits: str = ""

AVAILABLE_RACES = [
    Race(id="human", name="Человек",
         description="Сбалансированные характеристики.",
         bonuses={},
         physical_traits="Обычное тело: две руки, две ноги, голова."),
    Race(id="elf", name="Эльф",
         description="Ловкость и магия.",
         bonuses={"dexterity": 2, "wisdom": 2, "magic_defense": 1, "speed": 1},
         physical_traits="Высокий гуманоид с острыми ушами, магическая чувствительность."),
    Race(id="beastkin", name="Зверолюд",
         description="Сила и выносливость.",
         bonuses={"strength": 2, "vitality": 2, "defense": 2},
         physical_traits="Крепкий гуманоид со звериными чертами (хвост, уши)."),
    Race(id="slime", name="Слайм",
         description="Уникальные способности.",
         bonuses={"wisdom": 3, "luck": 2, "evasion": 5},
         physical_traits="Желеобразная субстанция. Нет конечностей. Действует через псевдоподии, телекинез.")
]

class PlayerStats(BaseModel):
    level: int = 1
    exp: int = 0
    hp: int = 100
    mp: int = 50
    strength: int = 10
    dexterity: int = 10
    intelligence: int = 10
    vitality: int = 10
    wisdom: int = 10
    luck: int = 10
    defense: int = 5
    magic_defense: int = 5
    speed: int = 10
    accuracy: int = 10
    evasion: int = 5
    crit_rate: float = 5.0
    crit_damage: float = 150.0
    hp_regen: int = 1
    mp_regen: int = 1
    charisma: int = 10

class Skill(BaseModel):
    name: str
    level: int = 1
    description: Optional[str] = ""               # краткое художественное описание
    category: Optional[str] = None
    effect: Optional[str] = ""                    # механика
    cost_mp: int = 0
    cast_time: float = 0.0
    cooldown: int = 0
    range: Optional[str] = "на себя"
    duration: Optional[str] = ""
    damage: Optional[str] = ""
    damage_type: Optional[str] = "none"
    requirements: Optional[str] = ""
    passive: bool = False

class InventoryItem(BaseModel):
    name: str
    description: str = ""
    type: str = "misc"
    equipped: bool = False
    damage: Optional[int] = None
    defense: Optional[int] = None
    stat_bonuses: Optional[Dict[str, int]] = None

class Enemy(BaseModel):
    id: str
    name: str
    health: int
    max_health: int
    damage: int
    type: str = "beast"

class Quest(BaseModel):
    id: str
    name: str
    description: str
    objectives: List[str] = Field(default_factory=list)
    completed: bool = False

# ---------- API Request/Response модели ----------
class CreateWorldRequest(BaseModel):
    name: str
    race_id: str

class SlotActionRequest(BaseModel):
    slot_id: str
    action: str

class GameResponse(BaseModel):
    narration: str
    world_state: Dict[str, Any]
    chat_history: Optional[List[Dict[str, str]]] = []

class WorldListItem(BaseModel):
    slot_id: str
    name: str
    player_name: str
    race: str
    level: int
    location: str

class GenerateSkillsRequest(BaseModel):
    name: str
    race_id: str

class GenerateSkillsResponse(BaseModel):
    skills: List[Skill]

class ChooseSkillsRequest(BaseModel):
    slot_id: str
    skills: List[Skill]

# ---------- Модели для интерактивной сцены ----------
class SceneMoveRequest(BaseModel):
    slot_id: str
    x: int
    y: int

class SceneInteractRequest(BaseModel):
    slot_id: str
    object_id: str
    action: str

class SceneObject(BaseModel):
    id: str
    type: str  # npc, enemy, chest, door, interactive
    name: str
    x: int
    y: int
    icon: str = "❓"
    hp: Optional[int] = None
    max_hp: Optional[int] = None
    damage: Optional[int] = None
    description: Optional[str] = ""
    interactions: List[str] = Field(default_factory=list)

class ScenePlayer(BaseModel):
    x: int
    y: int
    icon: str = "🧙"
    facing: str = "right"  # left, right, up, down

class SceneData(BaseModel):
    type: str  # room, outdoor, dungeon
    width: int = 800
    height: int = 600
    objects: List[SceneObject] = Field(default_factory=list)
    player: Optional[ScenePlayer] = None

class SceneResponse(BaseModel):
    scene: Optional[SceneData] = None
    error: Optional[str] = None