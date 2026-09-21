# Friday 2.0 - AI Desktop Mascot & Assistant

Friday 2.0 is an interactive, animated AI desktop companion powered by Live2D, multi-turn conversational intelligence, long-term semantic memory, and system automation tools.

---

## Architecture Overview

```
Friday2.0/
├── main.py                 # FastAPI backend orchestrator & WebSocket server
├── gui.py                  # CustomTkinter & pystray system tray desktop integration
├── backend.spec            # PyInstaller build specification
├── requirements.txt        # Python backend dependencies
├── .env.example            # Environment configuration template
│
├── memory/                 # Fast SQLite Memory Subsystem
│   ├── db.py               # SQLite structured interaction history & FTS5 search
│   ├── extractor.py        # Fact & preference extractor (LLM fallback)
│   ├── fast_extractor.py   # Ultra-fast local entity & preference extraction
│   └── summarizer.py       # Episodic conversation summarization
│
├── tools/                  # Desktop & Agent Automation Tools
│   ├── base_tools.py       # Core tool wrappers and registry
│   ├── system_tools.py     # Windows notifications & system queries
│   ├── windows_tools.py    # Windows OS automation & control
│   ├── file_tools.py       # Safe file system operations
│   ├── gui_tools.py        # Screen capture and GUI automation
│   └── memory_tools.py     # Tool bindings for memory querying
│
├── data/                   # Persistent runtime databases (git-ignored)
│   └── friday_memory.db    # SQLite memory database (FTS5 indexed)
│
└── web/                    # Desktop Frontend (Electron + Vite + React)
    ├── electron/           # Electron main process & IPC handlers
    ├── public/             # Static public assets served by Vite
    │   ├── audio/          # Runtime TTS audio cache (git-ignored)
    │   └── runtime/        # Live2D Character Models (e.g. Jian)
    │       └── jian/       # Live2D Cubism 4 model files & expressions
    ├── src/
    │   ├── characters/     # Mascot profiles and emotion mappings
    │   │   ├── index.ts    # Character export registry
    │   │   └── jian.ts     # Jian (简) character configuration
    │   ├── App.tsx         # Main mascot UI, audio, lip sync & interaction loop
    │   └── main.tsx        # React entrypoint
    └── package.json        # Frontend dependencies and build scripts
```

---

## Getting Started

### 1. Prerequisites
- **Node.js** (v18 or higher)
- **Python** (v3.10 to v3.12 recommended)
- **FFmpeg** (added to system PATH)

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your API keys:
```bash
cp .env.example .env
```
Supported providers:
- `GROQ_API_KEY`: Ultra-low-latency LLM inference
- `MISTRAL_API_KEY`: Advanced reasoning & tool execution
- `GEMINI_API_KEY`: Multimodal & general operations

### 3. Backend Setup
Create and activate a Python virtual environment:
```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
```
Install dependencies:
```bash
pip install -r requirements.txt
```

### 4. Frontend Setup
From the `web/` directory:
```bash
cd web
npm install
```

### 5. Running the Application
To start both the Electron window and the Python backend in development mode:
```bash
cd web
npm run dev
```

To build a standalone production executable:
```bash
# 1. Build the Python backend executable
pyinstaller backend.spec

# 2. Package the Electron application
cd web
npm run build:exe
```

---
## Reference video 



https://github.com/user-attachments/assets/55e4a9b3-648b-462a-8a7e-6d2263d40457



## Character & Live2D System

Character configurations are modularly organized inside `web/src/characters/`.
- **Active Mascot**: Jian (`web/src/characters/jian.ts`)
- **Assets**: Live2D Cubism 4 assets reside in `web/public/runtime/<character_id>/`
- Features include real-time lip sync to generated TTS speech, emotion-to-expression mapping, head physics tracking, drag-and-drop floating placement, and click-through idle mode.
