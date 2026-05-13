# Тесты для backend/memory.py

import pytest
import time
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from memory import LongTermMemory


class TestLongTermMemory:
    """Тесты для системы долговременной памяти."""

    @pytest.fixture
    def mock_chroma_client(self):
        """Фикстура мок-объекта Chroma клиента."""
        client = Mock()
        collection = Mock()
        collection.get.return_value = {'ids': [], 'metadatas': [], 'documents': []}
        client.get_or_create_collection.return_value = collection
        return client, collection

    @pytest.fixture
    def mock_embedding_client(self):
        """Фикстура мок-объекта embedding клиента."""
        client = Mock()
        client.embeddings.create = Mock(return_value=Mock(data=[Mock(embedding=[0.1] * 10)]))
        return client

    @patch('memory.chromadb.PersistentClient')
    @patch('memory.OpenAI')
    def test_initialization_success(self, mock_openai, mock_chroma, mock_chroma_client, mock_embedding_client):
        """Тест успешной инициализации памяти."""
        mock_chroma.return_value = mock_chroma_client[0]
        mock_openai.return_value = mock_embedding_client
        
        memory = LongTermMemory(slot_id="test_slot", disabled=False)
        
        assert memory.enabled is True
        assert memory.collection is not None
        mock_chroma.assert_called_once()

    @patch('memory.chromadb.PersistentClient')
    @patch('memory.OpenAI')
    def test_initialization_disabled(self, mock_openai, mock_chroma):
        """Тест инициализации в отключенном режиме."""
        memory = LongTermMemory(slot_id="test_slot", disabled=True)
        
        assert memory.enabled is False
        mock_chroma.assert_not_called()
        mock_openai.assert_not_called()

    @patch('memory.chromadb.PersistentClient')
    @patch('memory.OpenAI')
    def test_initialization_failure(self, mock_openai, mock_chroma):
        """Тест неудачной инициализации."""
        mock_chroma.side_effect = Exception("ChromaDB error")
        
        memory = LongTermMemory(slot_id="test_slot", disabled=False)
        
        assert memory.enabled is False

    @patch('memory.chromadb.PersistentClient')
    @patch('memory.OpenAI')
    def test_add_memory(self, mock_openai, mock_chroma, mock_chroma_client, mock_embedding_client):
        """Тест добавления воспоминания."""
        mock_chroma.return_value = mock_chroma_client[0]
        mock_openai.return_value = mock_embedding_client
        
        memory = LongTermMemory(slot_id="test_slot", disabled=False)
        mem_id = memory.add_memory("Тестовое воспоминание", {"type": "action"})
        
        assert mem_id is not None
        mock_chroma_client[1].upsert.assert_called_once()
        call_args = mock_chroma_client[1].upsert.call_args
        assert call_args[1]['documents'][0] == "Тестовое воспоминание"
        assert "timestamp" in call_args[1]['metadatas'][0]

    @patch('memory.chromadb.PersistentClient')
    @patch('memory.OpenAI')
    def test_add_memory_disabled(self, mock_openai, mock_chroma):
        """Тест добавления воспоминания в отключенном режиме."""
        memory = LongTermMemory(slot_id="test_slot", disabled=True)
        result = memory.add_memory("Тест")
        
        assert result is None

    @patch('memory.chromadb.PersistentClient')
    @patch('memory.OpenAI')
    def test_query_memory(self, mock_openai, mock_chroma, mock_chroma_client, mock_embedding_client):
        """Тест запроса воспоминаний."""
        mock_chroma.return_value = mock_chroma_client[0]
        mock_openai.return_value = mock_embedding_client
        mock_chroma_client[1].query.return_value = {
            'documents': [["Воспоминание 1", "Воспоминание 2"]]
        }
        
        memory = LongTermMemory(slot_id="test_slot", disabled=False)
        results = memory.query_memory("запрос", n_results=2)
        
        assert len(results) == 2
        assert results[0] == "Воспоминание 1"
        mock_chroma_client[1].query.assert_called_once()

    @patch('memory.chromadb.PersistentClient')
    @patch('memory.OpenAI')
    def test_query_memory_disabled(self, mock_openai, mock_chroma):
        """Тест запроса воспоминаний в отключенном режиме."""
        memory = LongTermMemory(slot_id="test_slot", disabled=True)
        results = memory.query_memory("запрос")
        
        assert results == []

    @patch('memory.chromadb.PersistentClient')
    @patch('memory.OpenAI')
    def test_delete_memories(self, mock_openai, mock_chroma, mock_chroma_client, mock_embedding_client):
        """Тест удаления воспоминаний."""
        mock_chroma.return_value = mock_chroma_client[0]
        mock_openai.return_value = mock_embedding_client
        
        memory = LongTermMemory(slot_id="test_slot", disabled=False)
        memory.delete_memories(["id1", "id2"])
        
        mock_chroma_client[1].delete.assert_called_once_with(ids=["id1", "id2"])

    @patch('memory.chromadb.PersistentClient')
    @patch('memory.OpenAI')
    def test_get_recent(self, mock_openai, mock_chroma, mock_chroma_client, mock_embedding_client):
        """Тест получения последних воспоминаний."""
        mock_chroma.return_value = mock_chroma_client[0]
        mock_openai.return_value = mock_embedding_client
        mock_chroma_client[1].get.return_value = {
            'ids': ['id1', 'id2'],
            'metadatas': [
                {"timestamp": time.time() - 100},
                {"timestamp": time.time()}
            ],
            'documents': ["Старое воспоминание", "Новое воспоминание"]
        }
        
        memory = LongTermMemory(slot_id="test_slot", disabled=False)
        results = memory.get_recent(n_results=2)
        
        assert len(results) == 2
        # Проверяем сортировку по времени (новое первое)
        assert results[0]["text"] == "Новое воспоминание"
        assert results[1]["text"] == "Старое воспоминание"

    @patch('memory.chromadb.PersistentClient')
    @patch('memory.OpenAI')
    def test_get_recent_disabled(self, mock_openai, mock_chroma):
        """Тест получения последних воспоминаний в отключенном режиме."""
        memory = LongTermMemory(slot_id="test_slot", disabled=True)
        results = memory.get_recent()
        
        assert results == []

    @patch('memory.chromadb.PersistentClient')
    @patch('memory.OpenAI')
    def test_cleanup_old_memories_ttl(self, mock_openai, mock_chroma, mock_chroma_client, mock_embedding_client):
        """Тест TTL очистки старых воспоминаний."""
        mock_chroma.return_value = mock_chroma_client[0]
        mock_openai.return_value = mock_embedding_client
        
        # Создаём старые воспоминания (старше 7 дней)
        old_timestamp = time.time() - (8 * 24 * 60 * 60)
        mock_chroma_client[1].get.return_value = {
            'ids': ['old1', 'old2', 'new1'],
            'metadatas': [
                {"timestamp": old_timestamp},
                {"timestamp": old_timestamp},
                {"timestamp": time.time()}
            ],
            'documents': ["Старое 1", "Старое 2", "Новое"]
        }
        
        memory = LongTermMemory(slot_id="test_slot", disabled=False)
        memory._cleanup_old_memories()
        
        # Должны быть удалены только старые
        mock_chroma_client[1].delete.assert_called_once()
        deleted_ids = mock_chroma_client[1].delete.call_args[1]['ids']
        assert 'old1' in deleted_ids
        assert 'old2' in deleted_ids
        assert 'new1' not in deleted_ids

    @patch('memory.chromadb.PersistentClient')
    @patch('memory.OpenAI')
    def test_cleanup_old_memories_limit(self, mock_openai, mock_chroma, mock_chroma_client, mock_embedding_client):
        """Тест очистки по лимиту размера."""
        mock_chroma.return_value = mock_chroma_client[0]
        mock_openai.return_value = mock_embedding_client
        
        # Создаём много воспоминаний (больше лимита MAX_MEMORIES_PER_SLOT=1000)
        ids = [f'id{i}' for i in range(1010)]
        metadatas = [{"timestamp": time.time() - i} for i in range(1010)]
        mock_chroma_client[1].get.return_value = {
            'ids': ids,
            'metadatas': metadatas,
            'documents': [f"doc{i}" for i in range(1010)]
        }
        
        memory = LongTermMemory(slot_id="test_slot", disabled=False)
        memory._cleanup_old_memories()
        
        # Должны быть удалены лишние
        mock_chroma_client[1].delete.assert_called_once()
        deleted_ids = mock_chroma_client[1].delete.call_args[1]['ids']
        assert len(deleted_ids) >= 10

    @patch('memory.chromadb.PersistentClient')
    @patch('memory.OpenAI')
    def test_embedding_failure(self, mock_openai, mock_chroma, mock_chroma_client):
        """Тест неудачного получения эмбеддинга."""
        mock_chroma.return_value = mock_chroma_client[0]
        mock_openai.return_value = Mock()
        mock_openai.return_value.embeddings.create.side_effect = Exception("Embedding failed")
        
        memory = LongTermMemory(slot_id="test_slot", disabled=False)
        
        # add_memory должен вернуть None при ошибке эмбеддинга
        result = memory.add_memory("Тест")
        assert result is None
        
        # query_memory должен вернуть пустой список при ошибке эмбеддинга
        results = memory.query_memory("запрос")
        assert results == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
