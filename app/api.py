import asyncio
import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from agent.event_stream import EventEmitter
from agent.orchestrator import AgentOrchestrator
from runtime.skills import load_all_skills
from runtime.skills.assets import load_skill_script
from runtime.storage import process_text

load_dotenv()

app = FastAPI(title="AI Demo System")

sessions: dict[str, tuple[EventEmitter, asyncio.Task]] = {}

FRONTEND_PATH = os.path.join(os.path.dirname(__file__), "web", "index.html")
_fund_review_splitter = load_skill_script("fund-review", "splitter.py")


class ChatRequest(BaseModel):
    message: str


@app.get("/", response_class=HTMLResponse)
async def index():
    with open(FRONTEND_PATH, "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/chat")
async def chat(request: ChatRequest):
    raw_text = request.message or ""

    doc = process_text(raw_text)
    numbered_text = _fund_review_splitter.format_to_numbered_text(doc)
    doc_id = doc["doc_id"]

    agent_message = (
        f"请审核以下基金经理评述。\n"
        f"文档 ID（doc_id）: {doc_id}\n"
        f"每行已带 [段落编号-句子编号] 标记。调用 Review 工具时，"
        f"请把下方编号文本完整作为 numbered_text 参数传入，"
        f"并把 doc_id 作为 doc_id 参数传入。\n"
        f"返回的每个 issue 的 global_s_id 必须形如 {doc_id}-p-s，"
        f"严格对应输入里实际命中的 [p-s] 标记。\n\n"
        f"{numbered_text}"
    )

    session_id = str(uuid.uuid4())
    emitter = EventEmitter()

    async def run_agent():
        orchestrator = AgentOrchestrator(
            emitter,
            doc=doc,
            numbered_text=numbered_text,
        )
        await orchestrator.run(agent_message)

    task = asyncio.create_task(run_agent())
    sessions[session_id] = (emitter, task)
    return JSONResponse({
        "session_id": session_id,
        "doc_id": doc_id,
        "paragraph_count": len(doc["paragraphs"]),
        "sentence_count": sum(len(p["sentences"]) for p in doc["paragraphs"]),
        "doc": doc,
    })


@app.post("/api/cancel/{session_id}")
async def cancel(session_id: str):
    entry = sessions.get(session_id)
    if not entry:
        return JSONResponse(
            {"cancelled": False, "reason": "session not found"},
            status_code=404,
        )
    _, task = entry
    if task.done():
        return JSONResponse({"cancelled": False, "reason": "already done"})
    task.cancel()
    return JSONResponse({"cancelled": True})


@app.get("/api/stream/{session_id}")
async def stream(session_id: str):
    entry = sessions.get(session_id)
    if not entry:
        return JSONResponse({"error": "session not found"}, status_code=404)
    emitter, _ = entry

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

