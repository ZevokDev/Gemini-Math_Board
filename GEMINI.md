# Pizarra: Math Tutoring AI

Pizarra is an interactive math tutoring web application that combines a handwriting-animated canvas frontend with a Gemini-powered backend. It allows students to solve math problems step-by-step through text input or real-time voice interaction.

## Project Overview

- **Purpose:** Provide a visual, AI-native math learning experience with step-by-step guidance.
- **Main Technologies:**
    - **Backend:** Python, FastAPI, Google Gemini API (`gemini-3.1-flash-lite-preview` for solving, `gemini-2.5-flash-native-audio-preview-12-2025` for Live API).
    - **Frontend:** HTML5 Canvas, Vanilla JavaScript, Web Audio API, WebSockets.
- **Architecture:** 
    - Single-file Python backend (`main.py`).
    - Single-file frontend (`static/index.html`).
    - Real-time bidirectional communication via WebSockets for voice mode.
    - Canvas-based rendering with specialized logic for different math visualization types (columns, long division, algebra, etc.).

## Building and Running

### Prerequisites
- Python 3.10+
- A Google Gemini API Key.

### Setup
1.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate
    ```
2.  **Install dependencies:**
    ```bash
    pip install fastapi uvicorn google-genai python-dotenv websockets pydantic
    ```
3.  **Configure Environment:**
    Create a `.env` file in the root directory:
    ```env
    GEMINI_API_KEY=your_api_key_here
    ```

### Running the App
```bash
uvicorn main:app --reload
```
Access the application at `http://localhost:8000`.

## Development Conventions

### Backend (`main.py`)
- **JSON Normalization:** All Gemini responses are normalized via `normalize_solution_payload` to ensure consistency in the frontend.
- **Visualization Inference:** If the model doesn't specify a `visualization_type`, the backend infers it from the problem text.
- **Voice Mode:** Uses `<STEPS>...</STEPS>` tags in the model's transcript to extract structured solution data during real-time conversations.

### Frontend (`static/index.html`)
- **Handwriting Animation:** All characters on the canvas are drawn stroke-by-stroke using a procedural tracing algorithm.
- **Renderers:** Drawing logic is modularized into a `renderers` map (e.g., `renderAdditionColumns`, `renderLongDivision`).
- **Styling:** Colors and fonts are managed via CSS custom properties and mirrored in JS for canvas use.
- **Timeline:** The `timeline-bar` allows users to navigate through steps, triggering re-renders with transitions.

### Testing
- Use the `/voice-text` WebSocket endpoint to test voice logic without a microphone.
- Check browser console for canvas rendering errors or WebSocket connection issues.

## TODO / Future Improvements
- [ ] Add formal `requirements.txt`.
- [ ] Implement unit tests for `normalize_solution_payload`.
- [ ] Support for more complex geometric visualizations.
- [ ] Improve handwriting stroke quality for specialized math symbols.
