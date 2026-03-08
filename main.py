import asyncio
import json
import os
import base64
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google import genai
from google.genai import types

load_dotenv()

app = FastAPI()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Existing /solve endpoint ---
class ProblemRequest(BaseModel):
    problem: str


VALID_LEVELS = {"primary", "middle-school", "high-school", "university"}
VALID_VISUALIZATION_TYPES = {
    "columns",
    "long-division",
    "live-equation",
    "factorization",
    "derivative",
    "integral",
}


def strip_json_fences(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def infer_visualization_type(problem: str, steps: list[dict] | None = None) -> str:
    haystack = " ".join(
        [problem.lower()] + [str(step.get("writing", "")).lower() for step in (steps or [])]
    )
    if any(token in haystack for token in ("∫", " integral", "integrate", "antiderivative")):
        return "integral"
    if any(token in haystack for token in ("d/d", "derivative", "differentiate")):
        return "derivative"
    if any(token in haystack for token in ("factor", "factored", "quadratic")):
        return "factorization"
    if any(token in haystack for token in ("÷", "/", " divided by ", "division")):
        return "long-division"
    if any(ch.isalpha() for ch in problem):
        return "live-equation"
    return "columns"


def infer_level(visualization_type: str) -> str:
    return {
        "columns": "primary",
        "long-division": "middle-school",
        "live-equation": "high-school",
        "factorization": "high-school",
        "derivative": "university",
        "integral": "university",
    }.get(visualization_type, "high-school")


def normalize_step(step: dict, index: int) -> dict:
    description = str(step.get("description") or f"Step {index + 1}")
    writing = str(step.get("writing") or "")
    action = str(step.get("action") or "Explain")
    highlight = step.get("highlight") or []
    if isinstance(highlight, str):
        highlight = [highlight]
    if not isinstance(highlight, list):
        highlight = []
    highlight = [str(item) for item in highlight if str(item).strip()]
    deeper_explanation = str(
        step.get("deeper_explanation")
        or step.get("deeperExplanation")
        or description
    )
    return {
        "description": description,
        "writing": writing,
        "action": action,
        "highlight": highlight,
        "deeper_explanation": deeper_explanation,
    }


def normalize_solution_payload(payload: dict, fallback_problem: str = "") -> dict:
    raw_steps = payload.get("steps") or []
    if not isinstance(raw_steps, list):
        raw_steps = []
    steps = [
        normalize_step(step, index)
        for index, step in enumerate(raw_steps)
        if isinstance(step, dict)
    ]
    problem = str(payload.get("problem") or fallback_problem)
    visualization_type = str(payload.get("visualization_type") or "").strip()
    if visualization_type not in VALID_VISUALIZATION_TYPES:
        visualization_type = infer_visualization_type(problem, steps)
    level = str(payload.get("level") or "").strip()
    if level not in VALID_LEVELS:
        level = infer_level(visualization_type)
    return {
        "problem": problem,
        "level": level,
        "visualization_type": visualization_type,
        "steps": steps,
    }

@app.post("/solve")
async def solve(req: ProblemRequest):
    async def get_text_solution():
        response = await client.aio.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=f"""
        You are a math teacher. Solve this problem step by step: {req.problem}

        Choose visualization_type based on the problem type:
        - "columns" for addition or subtraction of integers
        - "long-division" for division problems
        - "live-equation" for algebra, linear equations, and general symbolic solving
        - "factorization" for quadratic factoring
        - "derivative" for differentiation
        - "integral" for integration

        Respond ONLY with valid JSON, no markdown, no backticks, just raw JSON:
        {{
          "problem": "the original problem",
          "level": "primary | middle-school | high-school | university",
          "visualization_type": "columns | long-division | live-equation | factorization | derivative | integral",
          "steps": [
            {{
              "description": "what we are doing in this step",
              "writing": "the math expression written on the board",
              "action": "type of operation (e.g. Simplify, Subtract, Divide, Result)",
              "highlight": ["term1", "term2"],
              "deeper_explanation": "a simpler alternative explanation of this step for a confused student"
            }}
          ]
        }}
        """
        )
        text = strip_json_fences(response.text)
        return normalize_solution_payload(json.loads(text), req.problem)

    async def get_helper_image():
        try:
            resp = await client.aio.models.generate_content(
                model="gemini-3.1-flash-image-preview",
                contents=f"A clear, educational visual aid or formula diagram that helps explain this math problem: {req.problem}"
            )
            if resp.candidates and resp.candidates[0].content.parts:
                for p in resp.candidates[0].content.parts:
                    if p.inline_data:
                        return f"data:{p.inline_data.mime_type};base64," + base64.b64encode(p.inline_data.data).decode()
        except Exception as e:
            print(f"Image generation failed: {e}")
        return None

    solution, helper_image = await asyncio.gather(get_text_solution(), get_helper_image())
    solution["helper_image"] = helper_image
    return solution


# --- Live voice WebSocket ---
LIVE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"

SYSTEM_PROMPT = """
You are an enthusiastic math teacher named Nova.
If the student gives you a fresh math problem:
1. Explain what you are going to do step by step out loud, like a real teacher.
2. After your spoken explanation, output one JSON block wrapped in <STEPS> tags and nothing else inside those tags.
3. The JSON must use this exact shape:
<STEPS>{
  "problem": "original problem",
  "level": "primary | middle-school | high-school | university",
  "visualization_type": "columns | long-division | live-equation | factorization | derivative | integral",
  "steps": [
    {
      "description": "what happens in this step",
      "writing": "the math expression",
      "action": "operation type",
      "highlight": ["term1", "term2"],
      "deeper_explanation": "a simpler alternative explanation of this specific step"
    }
  ]
}</STEPS>
4. Choose visualization_type from these rules:
- columns: simple addition or subtraction
- long-division: division problems
- live-equation: algebra equations or symbolic rearranging
- factorization: quadratic factorization
- derivative: differentiation
- integral: integration

If the student is asking a follow-up question about a specific step or says they are confused:
- answer naturally with voice only
- do not emit a <STEPS> block unless they explicitly ask you to solve a brand-new problem

Keep your spoken explanation friendly, clear, and encouraging. Never use markdown.
"""

@app.websocket("/voice")
async def voice_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Voice WebSocket connected")

    live_config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": SYSTEM_PROMPT,
        "output_audio_transcription": {},
    }

    try:
        async with client.aio.live.connect(
            model=LIVE_MODEL,
            config=live_config
        ) as session:

            async def receive_from_browser():
                """Receive audio chunks from browser and forward to Gemini."""
                try:
                    while True:
                        message = await websocket.receive_json()
                        if message["type"] == "audio":
                            audio_bytes = base64.b64decode(message["data"])
                            await session.send_realtime_input(
                                audio=types.Blob(
                                    data=audio_bytes,
                                    mime_type="audio/pcm;rate=16000"
                                )
                            )
                        elif message["type"] == "stop":
                            break
                except WebSocketDisconnect:
                    pass

            async def receive_from_gemini():
                """Receive responses from Gemini and forward to browser."""
                transcript_buffer = ""
                try:
                    async for msg in session.receive():
                        sc = msg.server_content
                        if sc is None:
                            continue

                        # Send audio chunks to browser
                        if sc.model_turn:
                            for part in sc.model_turn.parts:
                                if part.inline_data:
                                    audio_b64 = base64.b64encode(
                                        part.inline_data.data
                                    ).decode()
                                    await websocket.send_json({
                                        "type": "audio",
                                        "data": audio_b64
                                    })

                        # Collect transcript and detect <STEPS> block
                        if sc.output_transcription:
                            chunk = sc.output_transcription.text
                            transcript_buffer += chunk
                            await websocket.send_json({
                                "type": "transcript",
                                "text": chunk
                            })

                            # Detect and extract steps JSON
                            if "<STEPS>" in transcript_buffer and "</STEPS>" in transcript_buffer:
                                start = transcript_buffer.index("<STEPS>") + 7
                                end = transcript_buffer.index("</STEPS>")
                                steps_json = transcript_buffer[start:end]
                                transcript_buffer = ""
                                try:
                                    steps_data = normalize_solution_payload(json.loads(steps_json))
                                    await websocket.send_json({
                                        "type": "steps",
                                        "data": steps_data
                                    })
                                    
                                    # Fire background image generation
                                    async def gen_image():
                                        try:
                                            img_resp = await client.aio.models.generate_content(
                                                model="gemini-3.1-flash-image-preview",
                                                contents=f"A clear, educational visual aid or formula diagram that helps explain this math problem: {steps_data['problem']}"
                                            )
                                            if img_resp.candidates and img_resp.candidates[0].content.parts:
                                                for p in img_resp.candidates[0].content.parts:
                                                    if p.inline_data:
                                                        img_data = f"data:{p.inline_data.mime_type};base64," + base64.b64encode(p.inline_data.data).decode()
                                                        await websocket.send_json({
                                                            "type": "image",
                                                            "data": img_data
                                                        })
                                        except Exception as e:
                                            print(f"WS Image generation failed: {e}")
                                    
                                    asyncio.create_task(gen_image())
                                    
                                except json.JSONDecodeError:
                                    pass

                        if sc.turn_complete:
                            await websocket.send_json({"type": "turn_complete"})

                except WebSocketDisconnect:
                    pass

            await asyncio.gather(
                receive_from_browser(),
                receive_from_gemini()
            )

    except Exception as e:
        print(f"Voice error: {e}")
        await websocket.close()

@app.websocket("/voice-text")
async def voice_text_endpoint(websocket: WebSocket):
    """Same as /voice but accepts text input instead of audio — for testing."""
    await websocket.accept()
    print("Voice-text WebSocket connected")

    live_config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": SYSTEM_PROMPT,
        "output_audio_transcription": {},
    }

    try:
        async with client.aio.live.connect(
            model=LIVE_MODEL,
            config=live_config
        ) as session:

            async def receive_from_browser():
                try:
                    while True:
                        message = await websocket.receive_json()
                        if message["type"] == "text":
                            await session.send_client_content(
                                turns=types.Content(
                                    role="user",
                                    parts=[types.Part(text=message["data"])]
                                )
                            )
                        elif message["type"] == "stop":
                            break
                except WebSocketDisconnect:
                    pass

            async def receive_from_gemini():
                transcript_buffer = ""
                try:
                    async for msg in session.receive():
                        sc = msg.server_content
                        if sc is None:
                            continue

                        if sc.model_turn:
                            for part in sc.model_turn.parts:
                                if part.inline_data:
                                    audio_b64 = base64.b64encode(
                                        part.inline_data.data
                                    ).decode()
                                    await websocket.send_json({
                                        "type": "audio",
                                        "data": audio_b64
                                    })

                        if sc.output_transcription:
                            chunk = sc.output_transcription.text
                            transcript_buffer += chunk
                            await websocket.send_json({
                                "type": "transcript",
                                "text": chunk
                            })

                            if "<STEPS>" in transcript_buffer and "</STEPS>" in transcript_buffer:
                                start = transcript_buffer.index("<STEPS>") + 7
                                end = transcript_buffer.index("</STEPS>")
                                steps_json = transcript_buffer[start:end]
                                transcript_buffer = ""
                                try:
                                    steps_data = normalize_solution_payload(json.loads(steps_json))
                                    await websocket.send_json({
                                        "type": "steps",
                                        "data": steps_data
                                    })
                                    
                                    # Fire background image generation
                                    async def gen_image():
                                        try:
                                            img_resp = await client.aio.models.generate_content(
                                                model="gemini-3.1-flash-image-preview",
                                                contents=f"A clear, educational visual aid or formula diagram that helps explain this math problem: {steps_data['problem']}"
                                            )
                                            if img_resp.candidates and img_resp.candidates[0].content.parts:
                                                for p in img_resp.candidates[0].content.parts:
                                                    if p.inline_data:
                                                        img_data = f"data:{p.inline_data.mime_type};base64," + base64.b64encode(p.inline_data.data).decode()
                                                        await websocket.send_json({
                                                            "type": "image",
                                                            "data": img_data
                                                        })
                                        except Exception as e:
                                            print(f"WS Image generation failed: {e}")
                                    
                                    asyncio.create_task(gen_image())
                                    
                                except json.JSONDecodeError:
                                    pass

                        if sc.turn_complete:
                            await websocket.send_json({"type": "turn_complete"})

                except WebSocketDisconnect:
                    pass

            await asyncio.gather(
                receive_from_browser(),
                receive_from_gemini()
            )

    except Exception as e:
        print(f"Voice-text error: {e}")
        await websocket.close()

app.mount("/", StaticFiles(directory="static", html=True), name="static")
