import os
from dotenv import load_dotenv

load_dotenv()  # загружаем .env из корня проекта

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:1234/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "lm-studio")
LLM_MODEL = os.getenv("LLM_MODEL", "gemma-4-e4b-uncensored")
SAVES_DIR = os.getenv("SAVES_DIR", "./saves")

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
WORLD_SAVE_FILE = os.getenv("WORLD_SAVE_FILE", "./world_state.json")
START_SKILLS_CHOICE_COUNT = int(os.getenv("START_SKILLS_CHOICE_COUNT", 5))

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-qwen3-embedding-4b")
