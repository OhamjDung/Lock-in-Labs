# Lock In Labs 🎮

A Life RPG that transforms personal goals into structured, gamified journeys. Build skill trees that break down aspirations into daily habits, track progress with XP rewards, and stay focused with AI-powered distraction detection.

## Features

### 🌳 Skill Tree System
- **Visual Progress Tracking**: Goals decompose into sub-skills and actionable daily habits
- **AI-Generated Trees**: Automatically creates personalized skill trees based on your goals
- **Four Life Pillars**: Organize goals across Career, Physical, Mental, and Social pillars
- **XP & Stats**: Earn experience points and level up as you complete habits and unlock skills

### 🔒 Lock-In Mode
- **Real-Time Distraction Detection**: Uses YOLOv11 computer vision to detect phones in your workspace
- **Focus Sessions**: Pomodoro-style timers with distraction monitoring
- **WebSocket-Based**: Low-latency communication for real-time alerts
- **Progress Tracking**: Monitor lock-in sessions and distraction patterns

### 🤖 AI-Powered Onboarding
- **"The Architect" Agent**: A conversational detective-style guide that helps you define goals
- **Voice & Text Input**: Support for both voice and text interaction modes
- **Structured Conversation**: Multi-phase onboarding that extracts goals, habits, and challenges

### 📊 Daily Reporting & Analytics
- **Progress Reflection**: Daily check-ins to update stats and track habit completion
- **Visual Dashboards**: Interactive charts showing skill progression, XP gains, and timelines
- **Task Scheduling**: Automated daily task generation based on skill tree habits

## Tech Stack

### Backend
- **FastAPI**: REST API and WebSocket server
- **Python 3.7+**: Core backend language
- **Google Gemini (genai)**: LLM for conversations and skill tree generation
- **Firebase Admin SDK**: User data persistence
- **YOLOv11 (Ultralytics)**: Real-time object detection for lock-in mode
- **OpenCV**: Video processing and webcam handling
- **Pydantic**: Type-safe data models

### Frontend
- **React 18**: UI framework
- **Vite**: Build tool and dev server
- **Tailwind CSS**: Styling
- **Recharts**: Data visualization
- **Firebase SDK**: Authentication and real-time sync
- **Web Speech API**: Voice input support

## Setup

### Prerequisites
- Python 3.7+
- Node.js 16+ and npm
- Firebase project (for authentication and data storage)
- Google Gemini API key
- (Optional) ElevenLabs API key for text-to-speech

### Backend Setup

1. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Download YOLO model**:
   - The YOLO model (`yolo11s.pt`) should be in the `phone-detector/` directory
   - If missing, Ultralytics will download it automatically on first use

3. **Configure environment variables**:
   Create a `.env` file in the project root:
   ```env
   # Required
   GEMINI_API_KEY=your-gemini-api-key
   FIREBASE_CREDENTIALS=path/to/firebase-credentials.json
   
   # Optional (for voice features)
   ELEVENLABS_API_KEY=your-elevenlabs-key
   ELEVENLABS_VOICE_ID=kqVT88a5QfII1HNAEPTJ
   ELEVENLABS_MODEL_ID=eleven_turbo_v2_5
   
   # Optional (for multiple API keys / rate limit handling)
   GEMINI_API_KEY_2=your-second-api-key
   GEMINI_MODEL=gemma-3-4b-it
   ```

4. **Firebase Setup**:
   - Download Firebase Admin SDK credentials JSON file
   - Set `FIREBASE_CREDENTIALS` environment variable to the path of this file
   - See `scripts/FIREBASE_CREDENTIALS_SETUP.md` for detailed instructions

### Frontend Setup

1. **Navigate to frontend directory**:
   ```bash
   cd frontend/test/life-rpg
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Configure environment variables**:
   Create a `.env` file in `frontend/test/life-rpg/`:
   ```env
   # Firebase Frontend Config (required)
   VITE_FIREBASE_API_KEY=your-api-key
   VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
   VITE_FIREBASE_PROJECT_ID=your-project-id
   VITE_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
   VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
   VITE_FIREBASE_APP_ID=your-app-id
   
   # Optional (for voice features)
   VITE_ELEVENLABS_API_KEY=your-elevenlabs-key
   ```

   See `frontend/test/life-rpg/GET_FIREBASE_CONFIG.md` for how to get these values.

## Running the Application

### Start Backend Server

In the project root:
```bash
uvicorn backend.api:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

### Start Frontend Dev Server

In `frontend/test/life-rpg/`:
```bash
npm run dev
```

The frontend will open at `http://localhost:5174`

### (Optional) Start Phone Detector Server

For lock-in mode phone detection:
```bash
cd phone-detector
python app.py --server --host 127.0.0.1 --port 9001
```

## Project Structure

```
├── backend/
│   └── api.py                 # FastAPI server with REST and WebSocket endpoints
├── frontend/test/life-rpg/
│   ├── src/
│   │   ├── components/        # React components
│   │   │   ├── dashboard/     # Profile, reporting, quests
│   │   │   ├── lockin/        # Lock-in mode UI
│   │   │   ├── onboarding/    # Onboarding flow
│   │   │   └── calendar/      # Calendar view
│   │   ├── config/
│   │   │   └── firebase.js    # Firebase configuration
│   │   └── LifeRPGInterface.jsx
│   └── package.json
├── phone-detector/
│   ├── app.py                 # YOLO phone detection server
│   └── yolo11s.pt            # YOLO model weights
├── src/
│   ├── models.py              # Pydantic data models
│   ├── llm.py                 # LLM client (Google Gemini)
│   ├── storage.py             # Firebase storage utilities
│   ├── onboarding/
│   │   ├── agent.py           # The Architect agent
│   │   └── prompts.py         # Onboarding prompts
│   ├── reporting/
│   │   ├── agent.py           # Reporting agent
│   │   ├── prompts.py         # Reporting prompts
│   │   └── scheduler.py       # Task scheduling logic
│   └── skill_tree/
│       └── generator.py       # Skill tree generation
├── scripts/                   # Utility scripts
└── requirements.txt           # Python dependencies
```

## Documentation

- **Project Description**: See `PROJECT_DESCRIPTION.md` for detailed project overview, challenges, and future plans
- **Firebase Setup**: `scripts/FIREBASE_CREDENTIALS_SETUP.md` for backend Firebase configuration
- **Frontend Firebase**: `frontend/test/life-rpg/FIREBASE_SETUP.md` and `GET_FIREBASE_CONFIG.md` for frontend setup
- **Phone Detector**: `phone-detector/README.md` for phone detection details

## Development

### Running Tests
```bash
python -m pytest tests/
```

### Adding New Features
- Backend API endpoints: Add to `backend/api.py`
- React components: Add to `frontend/test/life-rpg/src/components/`
- Data models: Update `src/models.py`
- LLM prompts: Update relevant prompt files in `src/onboarding/prompts.py` or `src/reporting/prompts.py`

## License

See LICENSE file for details.

## Contributing

Contributions welcome! Please open an issue or submit a pull request.
