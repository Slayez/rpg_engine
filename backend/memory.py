import hashlib, os, time, logging
from typing import Dict, List, Optional
import chromadb
from chromadb.config import Settings
from openai import OpenAI
from config import CHROMA_PERSIST_DIR, OPENAI_BASE_URL, OPENAI_API_KEY, EMBEDDING_MODEL

logger = logging.getLogger(__name__)

class LongTermMemory:
    def __init__(self, slot_id: str, disabled: bool = False):
        self.slot_id = slot_id
        self.persist_dir = os.path.join(CHROMA_PERSIST_DIR, f"slot_{slot_id}")
        self.client = None
        self.collection = None
        self.embedding_client = None
        self.enabled = False

        if disabled:
            logger.info(f"Memory disabled for slot {slot_id}")
            return

        try:
            os.makedirs(self.persist_dir, exist_ok=True)
            # Chroma PersistentClient
            self.client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False)
            )
            self.collection = self.client.get_or_create_collection("narrative_memory")
            # Embedding-клиент
            self.embedding_client = OpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)
            self.embedding_model = EMBEDDING_MODEL
            # Проверим, что embedding работает
            test_emb = self._get_embedding("test")
            if test_emb is None:
                raise RuntimeError("Embedding test failed")
            self.enabled = True
            logger.info(f"LongTermMemory initialized for slot {slot_id}")
        except Exception as e:
            logger.error(f"LongTermMemory initialization failed for slot {slot_id}: {e}")
            self.enabled = False

    def close(self):
        if self.client:
            try:
                del self.client
            except:
                pass

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        if not self.embedding_client:
            return None
        try:
            response = self.embedding_client.embeddings.create(
                model=self.embedding_model, input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return None

    def add_memory(self, text: str, metadata: Dict = None) -> Optional[str]:
        if not self.enabled:
            return None
        embedding = self._get_embedding(text)
        if embedding is None:
            return None
        mem_id = hashlib.md5(text.encode()).hexdigest()
        meta = metadata or {}
        meta["timestamp"] = time.time()
        try:
            self.collection.upsert(
                embeddings=[embedding],
                documents=[text],
                metadatas=[meta],
                ids=[mem_id]
            )
            return mem_id
        except Exception as e:
            logger.error(f"add_memory failed: {e}")
            return None

    def query_memory(self, query: str, n_results: int = 3) -> List[str]:
        if not self.enabled or not self.collection:
            return []
        embedding = self._get_embedding(query)
        if embedding is None:
            return []
        try:
            results = self.collection.query(query_embeddings=[embedding], n_results=n_results)
            docs = results.get('documents', [[]])
            return docs[0] if docs else []
        except Exception as e:
            logger.error(f"query_memory failed: {e}")
            return []

    def delete_memories(self, ids: List[str]):
        if ids and self.enabled and self.collection:
            try:
                self.collection.delete(ids=ids)
            except Exception as e:
                logger.error(f"delete_memories failed: {e}")

    def get_recent(self, n_results: int = 10) -> List[Dict]:
        """Возвращает последние n_results записей с сортировкой по времени."""
        if not self.enabled or not self.collection:
            return []
        try:
            existing = self.collection.get()
            ids = existing.get('ids', [])
            metadatas = existing.get('metadatas', [])
            documents = existing.get('documents', [])
            if not ids:
                return []
            items = []
            for i in range(len(ids)):
                meta = metadatas[i] if metadatas and i < len(metadatas) else {}
                ts = meta.get("timestamp", 0)
                items.append((ts, ids[i], documents[i], meta))
            items.sort(key=lambda x: x[0], reverse=True)
            recent = items[:n_results]
            return [{"id": x[1], "text": x[2], "metadata": x[3]} for x in recent]
        except Exception as e:
            logger.error(f"get_recent failed: {e}")
            return []