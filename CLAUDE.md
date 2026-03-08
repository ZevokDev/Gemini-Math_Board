# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate the venv first
source venv/bin/activate

# Run the server
uvicorn main:app --reload

# Install dependencies (no requirements.txt — install manually)
pip install fastapi uvicorn google-genai python-dotenv websockets pydantic
```

The app serves on `http://localhost:8000`. The frontend is at `static/index.html` and is served directly by FastAPI as static files.

## Environment

Requires a `.env` file with:
```
GEMINI_API_KEY=<your key>
```

## Architecture

This is a single-file Python backend (`main.py`) + single-file frontend (`static/index.html`). There are no separate JS modules, build tools, or bundlers.

**Backend (`main.py`)** — FastAPI app with three endpoints:
- `POST /solve` — Sends a math problem to Gemini (`gemini-3.1-flash-lite-preview`), returns a normalized JSON solution payload with steps.
- `WS /voice` — Real-time bidirectional WebSocket: receives raw PCM audio (16kHz, base64-encoded) from the browser, streams it to Gemini Live API (`gemini-2.5-flash-native-audio-preview-12-2025`), and streams back audio + transcript chunks. Detects `<STEPS>...</STEPS>` tags in the transcript to extract structured solution data.
- `WS /voice-text` — Same as `/voice` but accepts text input instead of audio (for testing without a microphone).

**Solution payload shape** (normalized by `normalize_solution_payload`):
```json
{
  "problem": "string",
  "level": "primary | middle-school | high-school | university",
  "visualization_type": "columns | long-division | live-equation | factorization | derivative | integral",
  "steps": [{ "description", "writing", "action", "highlight", "deeper_explanation" }]
}
```

**Frontend (`static/index.html`)** — Vanilla JS + HTML Canvas. No frameworks. Key concepts:
- All math visualization is drawn on a `<canvas>` element using a `renderers` map keyed by `visualization_type`.
- A step timeline UI lets users navigate through solution steps; each step triggers a canvas re-render with transitions/pulse animations.
- Voice mode uses `MediaRecorder` to capture mic audio, sends PCM chunks over the `/voice` WebSocket, and plays back audio responses via the Web Audio API.
- The "deeper explanation" feature shows an alternative step explanation in a panel below the board.
- Colors and fonts are defined as CSS custom properties (`--accent`, `--ink`, `--warm`, etc.) and mirrored as JS `COLORS` constants in the canvas renderer.

## Design Context

### Users
Pizarra is for a broad range of students, from children through university learners. The interface should stay intuitive enough for younger users while remaining credible and useful for more advanced students. The core job is to help learners understand math step by step through a guided, visual, and interactive experience rather than a dense static answer dump.

### Brand Personality
The product should feel simple, animated, and colorful. Its voice should remain friendly, patient, and clear, with the emotional goal of making students feel oriented, capable, and engaged. Interactions should feel lively and encouraging without becoming noisy or distracting.

### Aesthetic Direction
Use Photomath and Symbolab as loose reference points for educational clarity and math-solving utility, but push the product toward a more visual, AI-native experience. Favor strong visual guidance, approachable motion, and color that helps comprehension. Avoid interfaces that feel cluttered, over-tooled, or academically sterile. Support both light and dark modes, ideally adapting to system preference while preserving clarity and visual warmth in each theme.

### Design Principles
1. Make the next step obvious: use layout, color, and motion to guide attention through the learning flow.
2. Keep complexity behind the scenes: advanced capability is fine, but the visible interface should stay clean and easy for younger users to understand.
3. Teach visually first: prefer diagrams, step states, timeline cues, and board-like feedback over dense text blocks.
4. Use animation with purpose: motion should explain transitions, reinforce progress, and add delight without slowing task completion.
5. Design for range: every screen should work for both early learners and advanced students, balancing playfulness with academic trust.
6. Maintain accessible defaults: follow general accessibility best practices, preserve readable contrast, avoid color-only meaning, and treat reduced-friction usability as a baseline expectation.
