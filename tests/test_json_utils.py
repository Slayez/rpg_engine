# Тесты для backend/json_utils.py

import pytest
from json_utils import (
    extract_json, parse_intents, parse_skills,
    IntentSchema, SkillSchema, UseSkillIntent, AttackIntent,
    InteractIntent, MoveIntent, TalkIntent, RepeatSkillIntent, GenericIntent
)


class TestExtractJson:
    """Тесты для функции извлечения JSON."""

    def test_extract_json_from_code_block(self):
        """Тест извлечения JSON из markdown блока."""
        text = '```json\n{"narration": "Огонь горит"}\n```'
        result = extract_json(text)
        assert result == {"narration": "Огонь горит"}

    def test_extract_json_without_code_block(self):
        """Тест извлечения JSON без markdown разметки."""
        text = '{"narration": "Огонь горит"}'
        result = extract_json(text)
        assert result == {"narration": "Огонь горит"}

    def test_extract_json_with_surrounding_text(self):
        """Тест извлечения JSON с окружающим текстом."""
        text = 'Вот результат:\n{"narration": "Огонь горит"}\nКонец.'
        result = extract_json(text)
        assert result == {"narration": "Огонь горит"}

    def test_extract_json_repair(self):
        """Тест восстановления повреждённого JSON."""
        text = '{"narration": "Огонь горит",}'  # Лишняя запятая
        result = extract_json(text)
        assert result["narration"] == "Огонь горит"

    def test_extract_json_not_found(self):
        """Тест когда JSON не найден."""
        text = 'Просто текст без JSON'
        with pytest.raises(ValueError, match="JSON not found"):
            extract_json(text)


class TestParseIntents:
    """Тесты для парсинга интентов."""

    def test_parse_intents_empty(self):
        """Тест пустых данных."""
        result = parse_intents(None)
        assert len(result) == 1
        assert result[0]["action_type"] == "other"

    def test_parse_intents_string(self):
        """Тест строкового ввода."""
        result = parse_intents('непонятный текст')
        assert len(result) == 1
        assert result[0]["action_type"] == "other"

    def test_parse_intents_dict(self):
        """Тест одиночного словаря."""
        data = {"action_type": "use_skill", "skill_name": "Огонь", "target": "враг"}
        result = parse_intents(data)
        assert len(result) == 1
        assert result[0]["action_type"] == "use_skill"
        assert result[0]["skill_name"] == "Огонь"

    def test_parse_intents_list(self):
        """Тест списка интентов."""
        data = [
            {"action_type": "use_skill", "skill_name": "Огонь", "target": "враг"},
            {"action_type": "move", "direction": "север"}
        ]
        result = parse_intents(data)
        assert len(result) == 2
        assert result[0]["action_type"] == "use_skill"
        assert result[1]["action_type"] == "move"

    def test_parse_intents_use_skill(self):
        """Тест интента использования навыка."""
        data = [{"action_type": "use_skill", "skill_name": "Огненный шар", "target": "волк"}]
        result = parse_intents(data)
        assert len(result) == 1
        assert result[0]["skill_name"] == "Огненный шар"
        assert result[0]["target"] == "волк"

    def test_parse_intents_attack(self):
        """Тест интента атаки."""
        data = [{"action_type": "attack", "weapon_name": "Меч", "target": "волк"}]
        result = parse_intents(data)
        assert len(result) == 1
        assert result[0]["weapon_name"] == "Меч"
        assert result[0]["target"] == "волк"

    def test_parse_intents_interact(self):
        """Тест интента взаимодействия."""
        data = [{"action_type": "interact", "object": "сундук"}]
        result = parse_intents(data)
        assert len(result) == 1
        assert result[0]["object"] == "сундук"

    def test_parse_intents_move(self):
        """Тест интента перемещения."""
        data = [{"action_type": "move", "direction": "север"}]
        result = parse_intents(data)
        assert len(result) == 1
        assert result[0]["direction"] == "север"

    def test_parse_intents_talk(self):
        """Тест интента разговора."""
        data = [{"action_type": "talk", "target": "NPC"}]
        result = parse_intents(data)
        assert len(result) == 1
        assert result[0]["target"] == "NPC"

    def test_parse_intents_repeat_skill(self):
        """Тест интента повторения навыка."""
        data = [{
            "action_type": "repeat_skill",
            "skill_name": "Огненный шар",
            "target": "волк",
            "count": 3,
            "wait_cooldown": False
        }]
        result = parse_intents(data)
        assert len(result) == 1
        assert result[0]["count"] == 3
        assert result[0]["wait_cooldown"] is False

    def test_parse_intents_invalid_action_type(self):
        """Тест неизвестного типа действия."""
        data = [{"action_type": "unknown_action", "data": "test"}]
        result = parse_intents(data)
        assert len(result) == 1
        assert result[0]["action_type"] == "other"

    def test_parse_intents_fallback_on_validation_error(self):
        """Тест fallback при ошибке валидации."""
        data = [{"action_type": "use_skill"}]  # Отсутствует обязательное skill_name
        result = parse_intents(data)
        assert len(result) == 1
        assert result[0]["action_type"] == "use_skill" or result[0]["action_type"] == "other"


class TestParseSkills:
    """Тесты для парсинга навыков."""

    def test_parse_skills_empty(self):
        """Тест пустых данных."""
        result = parse_skills(None)
        assert result == []

    def test_parse_skills_valid(self):
        """Тест валидного навыка."""
        data = [{
            "name": "Огненный шар",
            "category": "Магия огня",
            "description": "Шар пламени",
            "effect": "3d6 урона огнём",
            "cost_mp": 15,
            "cast_time": 1.5,
            "cooldown": 4,
            "range": "20 м",
            "damage": "3d6",
            "damage_type": "fire"
        }]
        result = parse_skills(data)
        assert len(result) == 1
        assert result[0]["name"] == "Огненный шар"
        assert result[0]["damage_type"] == "fire"

    def test_parse_skills_invalid_damage_type(self):
        """Тест невалидного типа урона."""
        data = [{
            "name": "Навык",
            "category": "Тест",
            "description": "Описание",
            "effect": "Эффект",
            "cost_mp": 10,
            "cast_time": 1.0,
            "cooldown": 2,
            "range": "10 м",
            "damage_type": "invalid_type"
        }]
        result = parse_skills(data)
        assert len(result) == 1
        assert result[0]["damage_type"] == "none"

    def test_parse_skills_partial_parse(self):
        """Тест частичного парсинга с дефолтными значениями."""
        data = [{
            "name": "Неполный навык",
            "category": "Тест"
            # Остальные поля отсутствуют
        }]
        result = parse_skills(data)
        assert len(result) == 1
        assert result[0]["name"] == "Неполный навык"
        assert result[0]["cost_mp"] == 0
        assert result[0]["damage_type"] == "none"

    def test_parse_skills_multiple(self):
        """Тест множественных навыков."""
        data = [
            {
                "name": "Огненный шар",
                "category": "Магия огня",
                "description": "Шар пламени",
                "effect": "3d6 урона",
                "cost_mp": 15,
                "cast_time": 1.5,
                "cooldown": 4,
                "range": "20 м",
                "damage": "3d6",
                "damage_type": "fire"
            },
            {
                "name": "Ледяная стрела",
                "category": "Магия воды",
                "description": "Стрела изо льда",
                "effect": "2d8 урона холодом",
                "cost_mp": 10,
                "cast_time": 1.0,
                "cooldown": 3,
                "range": "15 м",
                "damage": "2d8",
                "damage_type": "water"
            }
        ]
        result = parse_skills(data)
        assert len(result) == 2
        assert result[0]["name"] == "Огненный шар"
        assert result[1]["name"] == "Ледяная стрела"

    def test_parse_skills_string_input(self):
        """Тест строкового ввода JSON."""
        json_str = '''[{
            "name": "Огненный шар",
            "category": "Магия огня",
            "description": "Шар пламени",
            "effect": "3d6 урона",
            "cost_mp": 15,
            "cast_time": 1.5,
            "cooldown": 4,
            "range": "20 м",
            "damage": "3d6",
            "damage_type": "fire"
        }]'''
        result = parse_skills(json_str)
        assert len(result) == 1
        assert result[0]["name"] == "Огненный шар"


class TestIntentSchemas:
    """Тесты Pydantic схем интентов."""

    def test_use_skill_intent_valid(self):
        """Тест валидного интента навыка."""
        intent = UseSkillIntent(action_type="use_skill", skill_name="Огонь", target="враг")
        assert intent.skill_name == "Огонь"
        assert intent.target == "враг"

    def test_use_skill_intent_empty_target(self):
        """Тест интента навыка без цели."""
        intent = UseSkillIntent(action_type="use_skill", skill_name="Огонь")
        assert intent.target == ""

    def test_attack_intent_valid(self):
        """Тест валидного интента атаки."""
        intent = AttackIntent(action_type="attack", weapon_name="Меч", target="волк")
        assert intent.weapon_name == "Меч"
        assert intent.target == "волк"

    def test_interact_intent_valid(self):
        """Тест валидного интента взаимодействия."""
        intent = InteractIntent(action_type="interact", object="сундук")
        assert intent.object == "сундук"

    def test_move_intent_valid(self):
        """Тест валидного интента перемещения."""
        intent = MoveIntent(action_type="move", direction="север")
        assert intent.direction == "север"

    def test_talk_intent_valid(self):
        """Тест валидного интента разговора."""
        intent = TalkIntent(action_type="talk", target="NPC")
        assert intent.target == "NPC"

    def test_repeat_skill_intent_valid(self):
        """Тест валидного интента повторения."""
        intent = RepeatSkillIntent(
            action_type="repeat_skill",
            skill_name="Огонь",
            count=3,
            wait_cooldown=False
        )
        assert intent.count == 3
        assert intent.wait_cooldown is False

    def test_repeat_skill_intent_count_limits(self):
        """Тест лимитов количества повторов."""
        # Слишком большое значение
        with pytest.raises(Exception):
            RepeatSkillIntent(action_type="repeat_skill", skill_name="Огонь", count=101)
        
        # Отрицательное значение
        with pytest.raises(Exception):
            RepeatSkillIntent(action_type="repeat_skill", skill_name="Огонь", count=0)

    def test_generic_intent_valid(self):
        """Тест валидного общего интента."""
        intent = GenericIntent(action_type="other", description="Действие")
        assert intent.description == "Действие"


class TestSkillSchema:
    """Тесты Pydantic схемы навыка."""

    def test_skill_schema_valid(self):
        """Тест валидного навыка."""
        skill = SkillSchema(
            name="Огненный шар",
            category="Магия огня",
            description="Шар пламени летит во врага",
            effect="3d6 урона огнём",
            cost_mp=15,
            cast_time=1.5,
            cooldown=4,
            range="20 м",
            damage="3d6",
            damage_type="fire"
        )
        assert skill.name == "Огненный шар"
        assert skill.damage_type == "fire"
        assert skill.passive is False

    def test_skill_schema_defaults(self):
        """Тест значений по умолчанию."""
        skill = SkillSchema(
            name="Навык",
            category="Тест",
            description="Описание",
            effect="Эффект",
            cost_mp=0,
            cast_time=0,
            cooldown=0,
            range="0 м"
        )
        assert skill.damage == "0"
        assert skill.damage_type == "none"
        assert skill.duration == ""
        assert skill.requirements == ""
        assert skill.passive is False

    def test_skill_schema_invalid_damage_type(self):
        """Тест невалидного типа урона."""
        skill = SkillSchema(
            name="Навык",
            category="Тест",
            description="Описание",
            effect="Эффект",
            cost_mp=0,
            cast_time=0,
            cooldown=0,
            range="0 м",
            damage_type="invalid"
        )
        assert skill.damage_type == "none"

    def test_skill_schema_valid_damage_types(self):
        """Тест валидных типов урона."""
        valid_types = ["physical", "magical", "fire", "water", "earth", "air", "heal", "none"]
        for dmg_type in valid_types:
            skill = SkillSchema(
                name="Навык",
                category="Тест",
                description="Описание",
                effect="Эффект",
                cost_mp=0,
                cast_time=0,
                cooldown=0,
                range="0 м",
                damage_type=dmg_type
            )
            assert skill.damage_type == dmg_type

    def test_skill_schema_field_constraints(self):
        """Тест ограничений полей."""
        # Пустое имя
        with pytest.raises(Exception):
            SkillSchema(
                name="",
                category="Тест",
                description="Описание",
                effect="Эффект",
                cost_mp=0,
                cast_time=0,
                cooldown=0,
                range="0 м"
            )
        
        # Отрицательный cost_mp
        with pytest.raises(Exception):
            SkillSchema(
                name="Навык",
                category="Тест",
                description="Описание",
                effect="Эффект",
                cost_mp=-10,
                cast_time=0,
                cooldown=0,
                range="0 м"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
