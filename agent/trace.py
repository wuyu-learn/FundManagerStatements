from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class TraceEvent:
    step_id: str
    status: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


class AgentTrace:
    def __init__(self):
        self.events: list[TraceEvent] = []

    def record(
        self,
        step_id: str,
        status: str,
        message: str,
        detail: Optional[dict[str, Any]] = None,
    ) -> TraceEvent:
        event = TraceEvent(
            step_id=step_id,
            status=status,
            message=message,
            detail=detail or {},
        )
        self.events.append(event)
        return event

    def to_dict(self) -> dict:
        return {"events": [event.to_dict() for event in self.events]}
