import os
import uuid
import asyncio
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

from agent.orchestrator import AgentOrchestrator
from agent.event_stream import EventEmitter
from mcp_server.skill_loader import load_all_skills

app = FastAPI(title="AI Demo System")

sessions: dict[str, EventEmitter] = {}

FRONTEND_PATH = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")


class ChatRequest(BaseModel):
    message: str


@app.get("/", response_class=HTMLResponse)
async def index():
    with open(FRONTEND_PATH, "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/chat")
async def chat(request: ChatRequest):
    session_id = str(uuid.uuid4())
    emitter = EventEmitter()
    sessions[session_id] = emitter

    async def run_agent():
        orchestrator = AgentOrchestrator(emitter)
        await orchestrator.run(request.message)

    asyncio.create_task(run_agent())
    return JSONResponse({"session_id": session_id})


@app.get("/api/stream/{session_id}")
async def stream(session_id: str):
    emitter = sessions.get(session_id)
    if not emitter:
        return JSONResponse({"error": "session not found"}, status_code=404)

    async def event_generator():
        while True:
            event = await emitter.get()
            yield emitter.to_sse_string(event)
            if (
                event.event_type.value == "final_answer"
                and event.data.get("content") == "__DONE__"
            ):
                sessions.pop(session_id, None)
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/skills")
async def list_skills():
    skills = load_all_skills()
    return JSONResponse([
        {
            "name": s.name,
            "description": s.description,
            "input_schema": s.input_schema,
            "output_schema": s.output_schema,
        }
        for s in skills
    ])
