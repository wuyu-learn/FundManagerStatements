import json
import asyncio
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class EventType(str, Enum):
    INTENT_DETECTED = "intent_detected"
    PLAN_CREATED = "plan_created"
    PLAN_STEP_STARTED = "plan_step_started"
    PLAN_STEP_COMPLETED = "plan_step_completed"
    AGENT_TRACE = "agent_trace"
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    SKILL_START = "skill_start"
    SKILL_END = "skill_end"
    REVIEW_ISSUES = "review_issues"   # P4：Review 校验后结构化推送给前端 col2
    FINAL_ANSWER = "final_answer"
    ERROR = "error"


@dataclass
class AgentEvent:
    event_type: EventType
    data: dict
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class EventEmitter:
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()

    async def emit(self, event_type: EventType, data: dict):
        event = AgentEvent(event_type=event_type, data=data)
        await self.queue.put(event)

    async def get(self) -> AgentEvent:
        return await self.queue.get()

    def to_sse_string(self, event: AgentEvent) -> str:
        payload = {
            "type": event.event_type.value,
            "data": event.data,
            "timestamp": event.timestamp,
        }
        return f"event: {event.event_type.value}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
