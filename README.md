# Character Creation Module

This project implements the "Smart" Character Creation Module as described in the roadmap.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure API Key:
   - Open `src/agent.py`.
   - The `LLMClient` class is currently using a **MOCK** implementation for demonstration purposes.
   - To use a real LLM (e.g., OpenAI), uncomment the OpenAI client initialization and the `chat.completions.create` call in `src/agent.py`.
   - Set your `OPENAI_API_KEY` environment variable.

## Running the App

Run the main script to start the interactive character creation loop:

```bash
python src/main.py
```

## Structure

- `src/models.py`: Pydantic data models (`CharacterSheet`, `ConversationState`).
- `src/prompts.py`: System prompts and few-shot examples for the Architect.
- `src/agent.py`: Logic for the `ArchitectAgent` (generation) and `CriticAgent` (analysis/extraction).
- `src/main.py`: The main game loop that orchestrates the conversation.
