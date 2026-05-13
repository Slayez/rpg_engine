# backend/db_storage.py
# SQLite + SQLAlchemy для атомарных сохранений и транзакций

import os, json, pickle
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import create_engine, Column, String, Text, Integer, Float, DateTime, LargeBinary, ForeignKey, event
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from config import SAVES_DIR

Base = declarative_base()


class SaveSlot(Base):
    __tablename__ = "save_slots"
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    world_state = Column(Text)  # JSON
    chat_history = Column(Text)  # JSON


class MemoryEntry(Base):
    __tablename__ = "memory_entries"
    id = Column(String, primary_key=True)
    slot_id = Column(String, ForeignKey("save_slots.id"), nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(LargeBinary)  # pickled list
    metadata_json = Column(Text)
    timestamp = Column(Float)
    
    slot = relationship("SaveSlot", backref="memories")


class DatabaseStorage:
    def __init__(self, slot_id: str):
        self.slot_id = slot_id
        self.db_path = os.path.join(SAVES_DIR, f"slot_{slot_id}", "game.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # SQLite WAL mode для лучшей параллельности
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        event.listen(self.engine, "connect", lambda conn, _: conn.execute("PRAGMA journal_mode=WAL"))
        
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.session = SessionLocal()
    
    def save_world_state(self, state: Dict[str, Any], chat_history: List[Dict]):
        """Атомарное сохранение мира и истории."""
        try:
            slot = self.session.query(SaveSlot).filter_by(id=self.slot_id).first()
            if not slot:
                slot = SaveSlot(id=self.slot_id)
                self.session.add(slot)
            
            slot.world_state = json.dumps(state, ensure_ascii=False)
            slot.chat_history = json.dumps(chat_history, ensure_ascii=False)
            slot.updated_at = datetime.utcnow()
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise e
    
    def load_world_state(self) -> Optional[Dict[str, Any]]:
        slot = self.session.query(SaveSlot).filter_by(id=self.slot_id).first()
        if slot and slot.world_state:
            return json.loads(slot.world_state)
        return None
    
    def load_chat_history(self) -> List[Dict]:
        slot = self.session.query(SaveSlot).filter_by(id=self.slot_id).first()
        if slot and slot.chat_history:
            return json.loads(slot.chat_history)
        return []
    
    def add_memory(self, text: str, embedding: List[float], metadata: Dict = None) -> str:
        import uuid, time
        mem_id = uuid.uuid4().hex
        entry = MemoryEntry(
            id=mem_id,
            slot_id=self.slot_id,
            text=text,
            embedding=pickle.dumps(embedding),
            metadata_json=json.dumps(metadata or {}),
            timestamp=time.time()
        )
        self.session.add(entry)
        self.session.commit()
        return mem_id
    
    def search_memories(self, query_embedding: List[float], n_results: int = 3) -> List[Dict]:
        """Поиск по косинусному сходству (упрощённо)."""
        entries = self.session.query(MemoryEntry).filter_by(slot_id=self.slot_id).all()
        results = []
        for e in entries:
            emb = pickle.loads(e.embedding) if e.embedding else []
            # Косинусное сходство
            dot = sum(a*b for a,b in zip(query_embedding, emb))
            norm_q = sum(x*x for x in query_embedding)**0.5
            norm_e = sum(x*x for x in emb)**0.5
            similarity = dot/(norm_q*norm_e) if norm_q and norm_e else 0
            results.append((similarity, e))
        results.sort(key=lambda x: -x[0])
        return [{"text": r[1].text, "metadata": json.loads(r[1].metadata_json), "similarity": r[0]} for r in results[:n_results]]
    
    def close(self):
        self.session.close()
    
    def export_slot(self) -> bytes:
        """Экспорт слота в .tar.gz архив."""
        import tarfile, io
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
            # Добавляем DB
            if os.path.exists(self.db_path):
                tar.add(self.db_path, arcname="game.db")
            # Добавляем Chroma если есть
            chroma_dir = os.path.join(SAVES_DIR, f"slot_{self.slot_id}", "chroma")
            if os.path.isdir(chroma_dir):
                tar.add(chroma_dir, arcname="chroma")
        return buffer.getvalue()
    
    def import_slot(self, archive_bytes: bytes):
        """Импорт слота из .tar.gz архива."""
        import tarfile, io, shutil
        buffer = io.BytesIO(archive_bytes)
        with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
            tar.extractall(path=os.path.join(SAVES_DIR, f"slot_{self.slot_id}"))
