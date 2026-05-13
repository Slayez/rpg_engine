# Документация схемы состояния игры

## Обзор

Этот документ описывает структуру состояния игры (WorldState), используемую в RPG с локальным LLM. Все компоненты backend обращаются к состоянию через единый интерфейс.

## Структура WorldState

### Корневые ключи

```python
{
    "location": str,                    # Текущая локация игрока
    "characters": {                     # Персонажи
        "player": PlayerCharacter,      # Игрок
        "npcs": [NPC]                   # NPC (опционально)
    },
    "enemies": [Enemy],                 # Враги в текущей сцене
    "environment_objects": {            # Объекты окружения
        "<id>": EnvironmentObject
    },
    "plot_flags": {                     # Флаги сюжета
        "analyzed_targets": {           # Проанализированные цели
            "<enemy_id>": bool
        }
    },
    "inventory": [Item],                # Инвентарь (опционально, дублирует characters.player.inventory)
    "quest_log": [Quest],               # Журнал заданий (опционально)
    "world_time": int,                  # Время в мире (в ходах/секундах)
    "combat_state": CombatState         # Состояние боя (если активен)
}
```

### PlayerCharacter

```python
{
    "name": str,                        # Имя персонажа
    "race": str,                        # ID расы (human, slime, elf, etc.)
    "level": int,                       # Уровень
    "experience": int,                  # Опыт
    "health": int,                      # Текущее HP
    "max_health": int,                  # Максимальное HP
    "mp": int,                          # Текущая MP
    "max_mp": int,                      # Максимальная MP
    "stats": {                          # Характеристики
        "strength": int,                # Сила
        "agility": int,                 # Ловкость
        "intelligence": int,            # Интеллект
        "vitality": int,                # Выносливость
        "hp": int,                      # HP от статов
        "mp": int                       # MP от статов
    },
    "skills": [Skill],                  # Список навыков
    "cooldowns": {                      # Активные кулдауны
        "<skill_name>": int             # Оставшиеся ходы
    },
    "inventory": [Item],                # Инвентарь
    "equipment": {                      # Экипировка
        "weapon": Item | None,
        "armor": Item | None,
        "accessory": Item | None
    },
    "status_effects": [StatusEffect],   # Активные эффекты
    "position": {                       # Позиция в мире/бою
        "x": int,
        "y": int
    }
}
```

### Skill

```python
{
    "name": str,                        # Название (1-50 символов)
    "category": str,                    # Категория навыка
    "description": str,                 # Художественное описание (до 200 символов)
    "effect": str,                      # Механика эффекта (до 100 символов)
    "cost_mp": int,                     # Расход MP (0-1000)
    "cast_time": float,                 # Время каста в секундах (0-60)
    "cooldown": int,                    # Перезарядка в секундах (0-300)
    "range": str,                       # Дальность ("5 м", "на себя", "10 м")
    "duration": str,                    # Длительность эффекта ("", "3 раунда", "10 сек")
    "damage": str,                      # Урон/лечение ("2d8", "120% маг. атаки", "0")
    "damage_type": str,                 # Тип урона
    "requirements": str,                # Требования ("", "Требуется меч")
    "passive": bool,                    # Пассивный ли навык
    "level": int                        # Уровень навыка (по умолчанию 1)
}
```

**Допустимые damage_type:**
- `physical` — физический урон
- `magical` — магический урон
- `fire` — огонь
- `water` — вода/лёд
- `earth` — земля/природа
- `air` — воздух/молния
- `heal` — лечение
- `none` — нет урона (дебафф, бафф, контроль)

### Enemy

```python
{
    "id": str,                          # Уникальный ID
    "name": str,                        # Название
    "level": int,                       # Уровень
    "health": int,                      # Текущее HP
    "max_health": int,                  # Максимальное HP
    "stats": {                          # Характеристики
        "strength": int,
        "agility": int,
        "intelligence": int,
        "vitality": int
    },
    "skills": [Skill],                  # Навыки врага
    "loot": [LootTable],                # Таблица добычи
    "behavior": str,                    # Тип поведения ("aggressive", "passive", "defensive")
    "position": {                       # Позиция в бою
        "x": int,
        "y": int
    },
    "status_effects": [StatusEffect],   # Активные эффекты
    "analyzed": bool                    # Проанализирован ли (+20% урона)
}
```

### EnvironmentObject

```python
{
    "id": str,                          # Уникальный ID (обычно name.lower().replace(" ", "_"))
    "name": str,                        # Название
    "type": str,                        # Тип ("tree", "rock", "chest", "door", etc.)
    "health": int,                      # Текущее "здоровье"
    "max_health": int,                  # Максимальное "здоровье"
    "interactable": bool,               # Можно ли взаимодействовать
    "description": str,                 # Описание для осмотра
    "loot": [Item] | None,              # Добыча при разрушении/вскрытии
    "position": {                       # Позиция
        "x": int,
        "y": int
    }
}
```

### Item

```python
{
    "id": str,                          # Уникальный ID
    "name": str,                        # Название
    "type": str,                        # Тип ("weapon", "armor", "consumable", "material", "quest")
    "rarity": str,                      # Редкость ("common", "uncommon", "rare", "epic", "legendary")
    "description": str,                 # Описание
    "effects": [Effect],                # Эффекты при использовании
    "equipped": bool,                   # Экипировано ли (для weapons/armor)
    "stack_size": int,                  # Размер стака (для consumable/material)
    "value": int,                       # Стоимость в золоте
    "requirements": {                   # Требования для использования
        "level": int,
        "strength": int,
        "intelligence": int
    }
}
```

### StatusEffect

```python
{
    "id": str,                          # Уникальный ID
    "name": str,                        # Название ("burn", "freeze", "buff_analyzed")
    "type": str,                        # Тип ("buff", "debuff", "dot", "hot")
    "duration": int,                    # Оставшаяся длительность (в ходах)
    "effect_value": int | float,        # Значение эффекта (+урон, -защита, etc.)
    "source": str,                      # Источник навыка/заклинания
    "tick_damage": int | None           # Урон/лечение каждый ход (для dot/hot)
}
```

### CombatState

```python
{
    "active": bool,                     # Активен ли бой
    "turn_order": [str],                # Порядок ходов (IDs участников)
    "current_turn": str,                # ID текущего ходящего
    "round": int,                       # Номер раунда
    "initiative": {                     # Инициатива участников
        "<id>": int
    },
    "battlefield": {                    # Поле боя
        "width": int,
        "height": int,
        "terrain": [TerrainTile]
    }
}
```

## Доступ к состоянию

### Чтение значений

```python
from world_state import WorldState

world = WorldState()

# Простое получение значения
hp = world.get("characters.player.health", 100)
skills = world.get("characters.player.skills", [])
enemies = world.get("enemies", [])

# Получение вложенных значений через точку
strength = world.get("characters.player.stats.strength", 10)
skill_cooldown = world.get("characters.player.cooldowns.Огненный шар", 0)
analyzed = world.get("plot_flags.analyzed_targets.wolf1", False)
```

### Запись значений

```python
# Обновление значения
world.update("characters.player.health", new_hp)
world.update("characters.player.mp", new_mp)
world.update("characters.player.cooldowns", updated_cooldowns)

# Обновление вложенного объекта
world.update("enemies.0.health", enemy_new_health)
world.update("environment_objects.tree_1.health", tree_new_health)
```

## Примеры использования

### Применение навыка

```python
# Проверка перед применением
skill = executor._get_skill_by_name("Огненный шар")
if not skill:
    return {"allowed": False, "reason": "Навык не найден"}

# Проверка MP
current_mp = world.get("characters.player.mp", 0)
if skill["cost_mp"] > current_mp:
    return {"allowed": False, "reason": "Недостаточно MP"}

# Проверка кулдауна
cooldowns = world.get("characters.player.cooldowns", {})
cd_left = cooldowns.get(skill["name"], 0)
if cd_left > 0:
    return {"allowed": False, "reason": "Навык на перезарядке"}

# Применение эффектов
updates = [
    {"key": "characters.player.mp", "value": current_mp - skill["cost_mp"]},
    {"key": "characters.player.cooldowns", "value": {**cooldowns, skill["name"]: skill["cooldown"]}}
]

# Если есть цель-враг
target_enemy = next((e for e in world.get("enemies", []) if e["name"].lower() == target_name.lower()), None)
if target_enemy:
    idx = world.get("enemies", []).index(target_enemy)
    new_health = target_enemy["health"] - damage
    updates.append({"key": f"enemies.{idx}.health", "value": new_health})
    
    if new_health <= 0:
        memory_entries.append(f"Враг {target_enemy['name']} повержен")
```

### Анализ врага

```python
# Проверка флага анализа
analyzed_flags = world.get("plot_flags.analyzed_targets", {})
is_analyzed = analyzed_flags.get(target_enemy_id, False)

if is_analyzed:
    damage_bonus = int(damage * 0.2)
    damage += damage_bonus
    
    # Сброс флага после атаки
    analyzed_flags.pop(target_enemy_id, None)
    updates.append({"key": "plot_flags.analyzed_targets", "value": analyzed_flags})

# Применение анализа новым навыком
if skill_is_analyze:
    analyzed_flags[target_enemy_id] = True
    updates.append({"key": "plot_flags.analyzed_targets", "value": analyzed_flags})
    memory_entries.append(f"Цель {target_name} проанализирована. +20% урона до конца боя.")
```

## Валидация данных

Все данные, записываемые в WorldState, должны проходить валидацию:

1. **Pydantic схемы** для сложных объектов (Skills, Items, Effects)
2. **Проверка типов** для примитивных значений
3. **Диапазоны значений** (HP >= 0, MP >= 0, cooldown >= 0)
4. **Ссылочная целостность** (существует ли enemy с данным ID)

## Кэширование и производительность

Для часто читаемых значений рекомендуется использовать кэш:

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_player_stat(world_snapshot_hash: str, stat_name: str) -> int:
    # Извлечение из снапшота
    ...
```

## Миграции схемы

При изменении структуры WorldState необходимо:

1. Добавить версию схемы (`schema_version: int`)
2. Реализовать миграционные функции
3. Обновить все места использования
4. Обновить эту документацию

---

**Версия документации:** 1.0  
**Последнее обновление:** 2024  
**Поддерживаемые версии схемы:** 1.x
