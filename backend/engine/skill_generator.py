# backend/engine/skill_generator.py

import json
import re
import logging
from typing import List, Dict, Any
from models import AVAILABLE_RACES, Skill
from system_prompt import SKILL_GENERATOR_PROMPT
from llm_client import LLMClient

logger = logging.getLogger(__name__)

ALLOWED_CATEGORIES = {
    "Магия огня", "Магия воды", "Магия земли", "Магия воздуха", "Магия пространства",
    "Универсальная магия", "Дальний бой", "Ближний бой", "Призыв",
    "Защита", "Скрытность", "Исцеление", "Бытовая магия", "Знания",
    "Ловкость", "Сила"
}

DEFAULT_SKILLS = [
    {
        "name": "Базовая атака",
        "level": 1,
        "description": "Обычная атака оружием.",
        "category": "Ближний бой",
        "effect": "Наносит 1d6 физического урона.",
        "cost_mp": 0,
        "cast_time": 0.0,
        "cooldown": 0,
        "range": "ближний бой",
        "duration": "",
        "damage": "1d6",
        "damage_type": "physical",
        "requirements": "",
        "passive": False
    },
    {
        "name": "Осторожность",
        "level": 1,
        "description": "Повышенное внимание.",
        "category": "Знания",
        "effect": "Пассивно увеличивает обнаружение скрытых объектов на 1.",
        "cost_mp": 0,
        "cast_time": 0.0,
        "cooldown": 0,
        "range": "",
        "duration": "",
        "damage": "0",
        "damage_type": "none",
        "requirements": "",
        "passive": True
    },
    {
        "name": "Выносливость",
        "level": 1,
        "description": "Лёгкий прилив сил.",
        "category": "Ловкость",
        "effect": "Восстанавливает 2 НР при низком здоровье.",
        "cost_mp": 5,
        "cast_time": 0.0,
        "cooldown": 12,
        "range": "на себя",
        "duration": "",
        "damage": "2",
        "damage_type": "heal",
        "requirements": "HP < 50%",
        "passive": False
    }
]


def guess_category(name: str, description: str) -> str:
    text = f"{name} {description}".lower()
    if any(w in text for w in ["огнен", "пламя", "огонь", "фаербол"]):
        return "Магия огня"
    if any(w in text for w in ["вод", "жидк", "волна", "капкан", "стена воды"]):
        return "Магия воды"
    if any(w in text for w in ["земл", "камен", "щит земли", "грязь"]):
        return "Магия земли"
    if any(w in text for w in ["воздух", "ветер", "порыв", "молния"]):
        return "Магия воздуха"
    if any(w in text for w in ["телепорт", "скачок", "перемещение"]):
        return "Магия пространства"
    if any(w in text for w in ["призыв", "дух", "страж", "помощник"]):
        return "Призыв"
    if any(w in text for w in ["скрыт", "тень", "незамет", "стелс"]):
        return "Скрытность"
    if any(w in text for w in ["леч", "восстанов", "здоровье", "роса"]):
        return "Исцеление"
    if any(w in text for w in ["защит", "щит", "барьер", "уклон"]):
        return "Защита"
    if any(w in text for w in ["лук", "стрельба", "дальний бой", "метатель"]):
        return "Дальний бой"
    if any(w in text for w in ["меч", "кинжал", "ближний бой", "удар"]):
        return "Ближний бой"
    if any(w in text for w in ["бытов", "шепот", "манипул", "предмет"]):
        return "Бытовая магия"
    if any(w in text for w in ["знани", "прониц", "распознав"]):
        return "Знания"
    if any(w in text for w in ["ловк", "гибк", "уклон"]):
        return "Ловкость"
    if any(w in text for w in ["универсаль", "луч", "энерг"]):
        return "Универсальная магия"
    if any(w in text for w in ["сил", "мощ", "мышц"]):
        return "Сила"
    return "Универсальная магия"


def parse_skills_from_raw(raw: str) -> List[Dict[str, Any]]:
    """Извлекает JSON массив навыков из сырого ответа LLM."""
    json_str = None
    
    # Пробуем найти блок ```json ... ```
    block_match = re.search(r'```json\s*(.*?)\s*```', raw, re.DOTALL)
    if block_match:
        json_str = block_match.group(1).strip()
    
    # Если не нашли в блоке, ищем любой JSON массив
    if not json_str:
        array_match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if array_match:
            json_str = array_match.group(0)
    
    # Если всё ещё не нашли, пробуем найти просто открывающую [ до конца строки
    if not json_str:
        bracket_start = raw.find('[')
        if bracket_start != -1:
            json_str = raw[bracket_start:]
    
    if not json_str:
        logger.warning(f"No JSON array found in raw response: {raw[:500]}")
        return []
    
    # Если JSON обрезан (нет закрывающей ]), пробуем восстановить
    if not json_str.rstrip().endswith(']'):
        logger.warning("JSON appears to be truncated, attempting to fix...")
        # Находим последнюю完整ную запись объекта
        last_brace = json_str.rfind('}')
        if last_brace != -1:
            json_str = json_str[:last_brace+1] + ']'
            logger.info("Attempted to fix truncated JSON by adding closing bracket")
    
    try:
        parsed = json.loads(json_str)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError as e:
        logger.warning(f"JSON decode failed: {e}, trying repair...")
        try:
            from json_repair import repair_json
            repaired = repair_json(json_str)
            parsed = json.loads(repaired)
            if isinstance(parsed, list):
                return parsed
        except ImportError:
            logger.warning("json_repair not available")
        except Exception as e2:
            logger.error(f"Repair also failed: {e2}")
    
    return []


def normalize_skill(s: Dict[str, Any]) -> Dict[str, Any]:
    """Приводит навык к стандартному формату."""
    name = s.get("name", "Неизвестный навык")
    category = s.get("category", "").strip()
    
    if not category or category not in ALLOWED_CATEGORIES:
        category = guess_category(name, s.get("effect", "") or s.get("description", ""))
    
    return {
        "name": name,
        "level": 1,
        "description": s.get("description", ""),
        "category": category,
        "effect": s.get("effect", ""),
        "cost_mp": int(s.get("cost_mp", 0)),
        "cast_time": float(s.get("cast_time", 0)),
        "cooldown": int(s.get("cooldown", 0)),
        "range": s.get("range", "на себя"),
        "duration": s.get("duration", ""),
        "damage": s.get("damage", "0"),
        "damage_type": s.get("damage_type", "none"),
        "requirements": s.get("requirements", ""),
        "passive": bool(s.get("passive", False))
    }


async def generate_start_skills(name: str, race_id: str) -> List[Dict[str, Any]]:
    """Генерирует стартовые навыки для персонажа через LLM."""
    race = next((r for r in AVAILABLE_RACES if r.id == race_id), None)
    race_name = race.name if race else race_id
    race_desc = race.physical_traits if race else ""
    
    context = (
        f"Персонаж: {name}, раса: {race_name} ({race_desc}). "
        "Сгенерируй ровно 20 стартовых навыков в виде JSON массива. Каждый навык — объект с полями "
        "name, category, description, effect, cost_mp, cast_time, cooldown, range, duration, damage, "
        "damage_type, requirements, passive."
    )
    
    messages = [
        {"role": "system", "content": SKILL_GENERATOR_PROMPT},
        {"role": "user", "content": context}
    ]
    
    llm = LLMClient()
    raw = await llm.completion(messages, max_tokens=4000, temperature=0.8)
    
    parsed_skills = parse_skills_from_raw(raw)
    
    if not parsed_skills:
        logger.error(f"Failed to parse generated skills, raw: {raw[:1000]}")
        return DEFAULT_SKILLS.copy()
    
    skills_out = [normalize_skill(s) for s in parsed_skills]
    logger.info(f"Generated {len(skills_out)} skills successfully")
    return skills_out