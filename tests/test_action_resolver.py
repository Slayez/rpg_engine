# Тесты для backend/engine/action_resolver.py

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock
from engine.action_resolver import IntentParser, ActionExecutor
from world_state import WorldState
from llm_client import LLMClient


class TestIntentParser:
    """Тесты для парсера интентов."""

    @pytest.fixture
    def mock_world(self):
        """Фикстура мок-объекта мира."""
        world = Mock(spec=WorldState)
        world.get.return_value = []
        return world

    @pytest.fixture
    def mock_llm(self):
        """Фикстура мок-объекта LLM клиента."""
        llm = Mock(spec=LLMClient)
        llm.completion = AsyncMock(return_value='[{"action_type": "use_skill", "skill_name": "Огонь", "target": "враг"}]')
        return llm

    @pytest.fixture
    def parser(self, mock_world, mock_llm):
        """Фикстура IntentParser."""
        return IntentParser(mock_world, mock_llm)

    @pytest.mark.asyncio
    async def test_extract_intents_repeat_pattern(self, parser, mock_world):
        """Тест парсинга повторяющихся действий без LLM."""
        action = "последовательно применяю Огненный шар ещё 3 раза на волка"
        intents = await parser.extract_intents(action)
        
        assert len(intents) == 1
        assert intents[0]["action_type"] == "repeat_skill"
        assert intents[0]["skill_name"] == "Огненный шар"
        assert intents[0]["count"] == 3
        assert intents[0]["target"] == "волк"
        assert intents[0]["wait_cooldown"] is False

    @pytest.mark.asyncio
    async def test_extract_intents_standard(self, parser, mock_llm):
        """Тест стандартного парсинга через LLM."""
        action = "использовать заклинание Огненный шар на дерево"
        intents = await parser.extract_intents(action)
        
        assert len(intents) == 1
        assert intents[0]["action_type"] == "use_skill"
        mock_llm.completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_intents_with_skills(self, parser, mock_world, mock_llm):
        """Тест парсинга с доступными навыками."""
        mock_world.get.return_value = [
            {"name": "Огненный шар"},
            {"name": "Ледяная стрела"}
        ]
        
        action = "атаковать огнём"
        await parser.extract_intents(action)
        
        # Проверяем, что навыки переданы в промпт
        call_args = mock_llm.completion.call_args
        assert "Огненный шар" in call_args[0][0][0]["content"]


class TestActionExecutor:
    """Тесты для исполнителя действий."""

    @pytest.fixture
    def mock_world(self):
        """Фикстура мок-объекта мира."""
        world = Mock(spec=WorldState)
        world.get.side_effect = lambda key, default=None: {
            "characters.player.skills": [
                {
                    "name": "Огненный шар",
                    "cost_mp": 15,
                    "cooldown": 4,
                    "damage": "3d6",
                    "damage_type": "fire"
                }
            ],
            "characters.player.mp": 50,
            "characters.player.cooldowns": {},
            "characters.player.health": 100,
            "characters.player.stats": {"strength": 10},
            "enemies": [{"id": "wolf1", "name": "Лесной волк", "health": 25, "max_health": 25}],
            "environment_objects": {},
            "plot_flags.analyzed_targets": {}
        }.get(key, default)
        return world

    @pytest.fixture
    def executor(self, mock_world):
        """Фикстура ActionExecutor."""
        return ActionExecutor(mock_world)

    def test_handle_skill_success(self, executor):
        """Тест успешного применения навыка."""
        intent = {"action_type": "use_skill", "skill_name": "Огненный шар", "target": "Лесной волк"}
        result = executor.execute_intent(intent)
        
        assert result["allowed"] is True
        assert "updates" in result
        assert "memory" in result
        assert "narrator_context" in result
        assert result["narrator_context"]["skill_used"] == "Огненный шар"
        assert result["narrator_context"]["mp_cost"] == 15

    def test_handle_skill_not_found(self, executor, mock_world):
        """Тест применения несуществующего навыка."""
        mock_world.get.side_effect = lambda key, default=None: {
            "characters.player.skills": [],
            "characters.player.mp": 50,
            "characters.player.cooldowns": {},
            "characters.player.health": 100,
            "characters.player.stats": {"strength": 10},
            "enemies": [],
            "environment_objects": {},
            "plot_flags.analyzed_targets": {}
        }.get(key, default)
        
        intent = {"action_type": "use_skill", "skill_name": "Несуществующий навык", "target": "враг"}
        result = executor.execute_intent(intent)
        
        assert result["allowed"] is False
        assert "не найден" in result["reason"].lower()

    def test_handle_skill_insufficient_mp(self, executor, mock_world):
        """Тест недостаточного количества MP."""
        mock_world.get.side_effect = lambda key, default=None: {
            "characters.player.skills": [
                {"name": "Огненный шар", "cost_mp": 100, "cooldown": 4, "damage": "3d6", "damage_type": "fire"}
            ],
            "characters.player.mp": 10,
            "characters.player.cooldowns": {},
            "characters.player.health": 100,
            "characters.player.stats": {"strength": 10},
            "enemies": [],
            "environment_objects": {},
            "plot_flags.analyzed_targets": {}
        }.get(key, default)
        
        intent = {"action_type": "use_skill", "skill_name": "Огненный шар", "target": "враг"}
        result = executor.execute_intent(intent)
        
        assert result["allowed"] is False
        assert "MP" in result["reason"] or "mp" in result["reason"].lower()

    def test_handle_skill_on_cooldown(self, executor, mock_world):
        """Тест навыка на перезарядке."""
        mock_world.get.side_effect = lambda key, default=None: {
            "characters.player.skills": [
                {"name": "Огненный шар", "cost_mp": 15, "cooldown": 4, "damage": "3d6", "damage_type": "fire"}
            ],
            "characters.player.mp": 50,
            "characters.player.cooldowns": {"Огненный шар": 2},
            "characters.player.health": 100,
            "characters.player.stats": {"strength": 10},
            "enemies": [],
            "environment_objects": {},
            "plot_flags.analyzed_targets": {}
        }.get(key, default)
        
        intent = {"action_type": "use_skill", "skill_name": "Огненный шар", "target": "враг"}
        result = executor.execute_intent(intent)
        
        assert result["allowed"] is False
        assert "перезарядк" in result["reason"].lower()

    def test_handle_attack_success(self, executor, mock_world):
        """Тест успешной атаки оружием."""
        mock_world.get.side_effect = lambda key, default=None: {
            "characters.player.skills": [],
            "characters.player.inventory": [
                {"name": "Ржавый меч", "type": "weapon", "damage": 8, "equipped": True}
            ],
            "characters.player.stats": {"strength": 10},
            "enemies": [{"id": "wolf1", "name": "Лесной волк", "health": 25, "max_health": 25}],
            "environment_objects": {}
        }.get(key, default)
        
        intent = {"action_type": "attack", "weapon_name": "Ржавый меч", "target": "Лесной волк"}
        result = executor.execute_intent(intent)
        
        assert result["allowed"] is True
        assert "updates" in result
        assert result["narrator_context"]["attack"] is True

    def test_handle_attack_no_weapon(self, executor, mock_world):
        """Тест атаки без оружия."""
        mock_world.get.side_effect = lambda key, default=None: {
            "characters.player.skills": [],
            "characters.player.inventory": [],
            "characters.player.stats": {"strength": 10},
            "enemies": [],
            "environment_objects": {}
        }.get(key, default)
        
        intent = {"action_type": "attack", "weapon_name": "Меч", "target": "враг"}
        result = executor.execute_intent(intent)
        
        assert result["allowed"] is False
        assert "оруж" in result["reason"].lower()

    def test_handle_move(self, executor):
        """Тест перемещения."""
        intent = {"action_type": "move", "direction": "север"}
        result = executor.execute_intent(intent)
        
        assert result["allowed"] is True
        assert any(u["key"] == "location" for u in result["updates"])

    def test_handle_interact(self, executor):
        """Тест взаимодействия с объектом."""
        intent = {"action_type": "interact", "object": "сундук"}
        result = executor.execute_intent(intent)
        
        assert result["allowed"] is True
        assert "interact_with" in result["narrator_context"]

    def test_normalize_skill_name(self, executor):
        """Тест нормализации названия навыка."""
        assert executor._normalize_skill_name("Огненный шар (улучшенный)") == "огненный шар"
        assert executor._normalize_skill_name("  Ледяная   стрела  ") == "ледяная стрела"

    def test_is_analyze_skill(self, executor):
        """Тест распознавания аналитических навыков."""
        analyze_skill = {"name": "Анализ врага", "description": "Изучает слабости", "effect": "+20% к урону", "category": "знания"}
        normal_skill = {"name": "Огненный шар", "description": "Шар пламени", "effect": "3d6 урона", "category": "магия огня"}
        
        assert executor._is_analyze_skill(analyze_skill) is True
        assert executor._is_analyze_skill(normal_skill) is False


class TestRepeatSkillIntent:
    """Тесты для обработки повторяющихся навыков."""

    @pytest.fixture
    def mock_world(self):
        """Фикстура мок-объекта мира."""
        world = Mock(spec=WorldState)
        world.get.side_effect = lambda key, default=None: {
            "characters.player.skills": [
                {"name": "Огненный шар", "cost_mp": 15, "cooldown": 4, "damage": "3d6", "damage_type": "fire"}
            ],
            "characters.player.mp": 100,
            "characters.player.cooldowns": {},
            "characters.player.health": 100,
            "characters.player.stats": {"strength": 10},
            "enemies": [{"id": "wolf1", "name": "Лесной волк", "health": 25, "max_health": 25}],
            "environment_objects": {},
            "plot_flags.analyzed_targets": {}
        }.get(key, default)
        return world

    @pytest.fixture
    def executor(self, mock_world):
        """Фикстура ActionExecutor."""
        return ActionExecutor(mock_world)

    def test_repeat_skill_requires_async(self, executor):
        """Тест что повтор навыка требует async обработки."""
        intent = {
            "action_type": "repeat_skill",
            "skill_name": "Огненный шар",
            "target": "Лесной волк",
            "count": 3,
            "wait_cooldown": False
        }
        result = executor.execute_intent(intent)
        
        assert result["requires_async"] is True
        assert result["intent"] == intent


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
