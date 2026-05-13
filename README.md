# Narrative Engine RPG

An AI-powered interactive narrative game engine that generates dynamic storylines using Large Language Models (LLMs). Built with FastAPI backend and React frontend.

## Features

- 🎮 **Interactive Storytelling** - AI-generated narrative responses to player actions
- 🌍 **Dynamic World State** - Persistent game world with state management
- 💾 **Save/Load System** - Multiple save slots for different game sessions
- 🎯 **Skill System** - Racial attributes and starting skill selection
- 🧠 **Memory System** - ChromaDB-based memory for contextual storytelling
- ⚡ **Streaming Responses** - Real-time streaming of AI-generated content
- 🔧 **Action Management** - Undo, retry, and edit previous actions

## Project Structure

```
/workspace
├── backend/                 # FastAPI backend
│   ├── main.py             # API endpoints
│   ├── game_manager.py     # Game session management
│   ├── engine/             # Game engine logic
│   ├── models.py           # Pydantic data models
│   ├── config.py           # Configuration settings
│   ├── llm_client.py       # LLM integration
│   ├── memory.py           # ChromaDB memory system
│   ├── world_state.py      # World state management
│   └── requirements.txt    # Python dependencies
├── frontend/               # React frontend
│   ├── src/                # React components
│   ├── public/             # Static assets
│   └── package.json        # Node.js dependencies
├── run.py                  # Combined server launcher
└── .env                    # Environment configuration
```

## Prerequisites

- **Python 3.8+**
- **Node.js 16+**
- **npm**

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd <project-directory>
```

### 2. Backend Setup

```bash
cd backend
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
cd frontend
npm install
```

### 4. Environment Configuration

Create a `.env` file in the root directory:

```env
# Backend Configuration
BACKEND_PORT=8000
FRONTEND_PORT=3000

# LLM API Key (e.g., OpenAI, DeepSeek)
OPENAI_API_KEY=your-api-key-here

# Optional: Custom model settings
MODEL_NAME=gpt-3.5-turbo
TEMPERATURE=0.7
```

## Running the Application

### Option 1: Combined Launch (Recommended)

Run both backend and frontend simultaneously:

```bash
python run.py
```

### Option 2: Separate Servers

**Backend:**
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm start
```

## Access the Application

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/saves` | List all saved worlds |
| POST | `/saves` | Create a new world/save |
| DELETE | `/saves/{slot_id}` | Delete a save |
| POST | `/generate-start-skills` | Generate starting skills for a character |
| POST | `/choose-start-skills` | Select starting skills |
| GET | `/world` | Get current world state |
| POST | `/action/stream` | Stream action response |
| POST | `/action/undo` | Undo last action |
| POST | `/action/retry` | Retry last action |
| POST | `/action/edit` | Edit last action |
| GET | `/memory` | Get recent memories |

## Configuration

### Backend (`backend/config.py`)

- `START_SKILLS_CHOICE_COUNT` - Number of skills to choose at game start
- Model parameters and LLM settings

### Frontend (`frontend/package.json`)

- Proxy configuration for API requests
- Build settings

## Development

### Backend Development

```bash
cd backend
uvicorn main:app --reload
```

### Frontend Development

```bash
cd frontend
npm start
```

## Technologies Used

**Backend:**
- FastAPI - Modern Python web framework
- Pydantic - Data validation
- OpenAI/LLM Client - AI text generation
- ChromaDB - Vector database for memory
- Transformers - ML models
- python-dotenv - Environment management

**Frontend:**
- React 18 - UI library
- React Markdown - Markdown rendering
- remark-gfm - GitHub Flavored Markdown support

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

---

**Note:** Make sure to configure your LLM API key in the `.env` file before running the application.
