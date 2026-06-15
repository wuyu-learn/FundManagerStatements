import json
import os
import asyncio
from typing import Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

from config import get_llm_settings
from .event_stream import EventEmitter, EventType
from .intents import IntentRecognizer, IntentResult
from .planner import PlanStep, TaskPlan, TaskPlanner
from .prompts import FINAL_REPORT_SYSTEM_PROMPT
from .trace import AgentTrace
from .validators import ReviewObservationValidator
from skill_runtime import run_skill

load_dotenv()

LLM_SETTINGS = get_llm_settings()
LLM_MODEL = LLM_SETTINGS["model"]

openai_client = AsyncOpenAI(
    api_key=LLM_SETTINGS["api_key"],
    base_url=LLM_SETTINGS["base_url"],
)


class AgentOrchestrator:
    """Controlled, explainable Agent for the statement-review workflow."""

    def __init__(
        self,
        emitter: EventEmitter,
        doc: Optional[dict] = None,
        numbered_text: Optional[str] = None,
    ):
        self.emitter = emitter
        self.doc = doc
        self.numbered_text = numbered_text or ""
        self.intent_recognizer = IntentRecognizer()
        self.planner = TaskPlanner()
        self.validator = ReviewObservationValidator(doc)
        self.trace = AgentTrace()

    async def _emit_trace_event(self, event):
        await self.emitter.emit(EventType.AGENT_TRACE, {
            "event": event.to_dict(),
            "trace": self.trace.to_dict(),
        })

    async def _start_step(self, step: PlanStep):
        event = self.trace.record(step.id, "running", f"开始：{step.name}", {
            "executor": step.executor,
            "purpose": step.purpose,
        })
        await self.emitter.emit(EventType.PLAN_STEP_STARTED, {
            "step": step.to_dict(),
            "trace_event": event.to_dict(),
        })
        await self._emit_trace_event(event)

    async def _complete_step(self, step: PlanStep, message: str, detail: Optional[dict] = None):
        event = self.trace.record(step.id, "completed", message, detail or {})
        await self.emitter.emit(EventType.PLAN_STEP_COMPLETED, {
            "step": step.to_dict(),
            "trace_event": event.to_dict(),
        })
        await self._emit_trace_event(event)

    async def _fail_step(self, step: PlanStep, message: str, detail: Optional[dict] = None):
        event = self.trace.record(step.id, "failed", message, detail or {})
        await self.emitter.emit(EventType.PLAN_STEP_COMPLETED, {
            "step": step.to_dict(),
            "trace_event": event.to_dict(),
        })
        await self._emit_trace_event(event)
        await self.emitter.emit(EventType.ERROR, {"message": message})

    async def _detect_intent(self, user_input: str) -> IntentResult:
        intent = self.intent_recognizer.recognize(user_input)
        event = self.trace.record("intent_detection", "completed", intent.display_name, {
            "intent": intent.to_dict(),
        })
        await self.emitter.emit(EventType.INTENT_DETECTED, {
            "intent": intent.to_dict(),
            "trace_event": event.to_dict(),
        })
        await self._emit_trace_event(event)
        if not intent.supported:
            await self.emitter.emit(EventType.ERROR, {
                "message": f"不支持的任务意图：{intent.display_name}"
            })
        return intent

    async def _create_plan(self, intent: IntentResult) -> TaskPlan:
        plan = self.planner.create_plan(intent)
        event = self.trace.record("planning", "completed", "已生成标准审核计划", {
            "plan": plan.to_dict(),
        })
        await self.emitter.emit(EventType.PLAN_CREATED, {
            "plan": plan.to_dict(),
            "trace_event": event.to_dict(),
        })
        await self._emit_trace_event(event)
        return plan

    async def _run_review_skill(self, step: PlanStep) -> str:
        await self._start_step(step)
        doc_id = self.doc.get("doc_id") if self.doc else ""
        action_input = {
            "numbered_text": self.numbered_text,
            "doc_id": doc_id,
        }

        await self.emitter.emit(EventType.THOUGHT, {
            "content": "开始调用 Review Skill 进行结构化审核",
            "iteration": 1,
        })
        await self.emitter.emit(EventType.ACTION, {
            "tool": "Review",
            "input": action_input,
            "iteration": 1,
        })
        await self.emitter.emit(EventType.SKILL_START, {"skill": "Review"})

        try:
            input_dump = json.dumps(action_input, ensure_ascii=False)
        except Exception:
            input_dump = repr(action_input)
        print(
            f"[orchestrator] → Skill: Review | input ({len(input_dump)} chars): {input_dump[:800]}",
            flush=True,
        )

        try:
            observation = await run_skill("Review", action_input)
        except Exception as e:
            await self._fail_step(step, f"Skill 调用失败: {e}")
            raise

        print(
            f"[orchestrator] ← Skill: Review | observation ({len(observation)} chars): {observation[:1500]}",
            flush=True,
        )
        await self.emitter.emit(EventType.SKILL_END, {
            "skill": "Review",
            "output_preview": observation[:300],
        })
        await self.emitter.emit(EventType.OBSERVATION, {
            "tool": "Review",
            "content": observation,
            "iteration": 1,
        })
        await self._complete_step(step, "Review Skill 已完成", {
            "output_preview": observation[:300],
        })
        return observation

    async def _validate_review_issues(self, step: PlanStep, observation: str) -> tuple[str, Optional[dict]]:
        await self._start_step(step)
        observation, parsed_obs, stats = self.validator.validate(observation)

        if stats["fixed_short"] or stats["hallucinated"]:
            parts = []
            if stats["fixed_short"]:
                parts.append(f"自动补全 {stats['fixed_short']} 个短 ID")
            if stats["hallucinated"]:
                sample = ", ".join(stats["hallucinated"][:3])
                more = "..." if len(stats["hallucinated"]) > 3 else ""
                parts.append(f"剔除 {len(stats['hallucinated'])} 个幻觉 ID ({sample}{more})")
            print(f"[orchestrator] Review 输出校验: {'；'.join(parts)}", flush=True)

        await self._complete_step(step, "问题定位校验完成", stats)
        return observation, parsed_obs

    async def _emit_review_issues(self, step: PlanStep, parsed_obs: Optional[dict]):
        await self._start_step(step)
        if not isinstance(parsed_obs, dict) or (
            "issues" not in parsed_obs and "summary" not in parsed_obs
        ):
            await self._complete_step(step, "Review 未返回结构化 issues", {
                "issue_count": 0,
            })
            return

        issues_list = parsed_obs.get("issues", [])
        if not isinstance(issues_list, list):
            issues_list = []
        summary_text = parsed_obs.get("summary", "")
        if not isinstance(summary_text, str):
            summary_text = str(summary_text)

        await self.emitter.emit(EventType.REVIEW_ISSUES, {
            "tool": "Review",
            "issues": issues_list,
            "summary": summary_text,
        })
        await self._complete_step(step, "审核反馈已推送", {
            "issue_count": len(issues_list),
            "summary": summary_text,
        })

    async def _generate_final_report(self, step: PlanStep, user_input: str, observation: str):
        await self._start_step(step)
        messages = [
            {"role": "system", "content": FINAL_REPORT_SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
            {"role": "user", "content": f"Observation: {observation}"},
        ]
        response = await openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            await self._fail_step(step, "LLM 返回格式错误", {"raw": raw})
            return

        action = parsed.get("action", "")
        action_input = parsed.get("action_input", {})
        if action != "final_answer":
            await self._fail_step(step, f"LLM 未按预期返回 final_answer: {action}")
            return

        answer = action_input.get("answer", "")
        await self.emitter.emit(EventType.THOUGHT, {
            "content": parsed.get("thought", "已完成审核"),
            "iteration": 2,
        })
        await self.emitter.emit(EventType.FINAL_ANSWER, {"content": answer})
        await self._complete_step(step, "完整审核报告已生成", {
            "answer_preview": answer[:120],
        })

    async def run(self, user_input: str):
        try:
            intent = await self._detect_intent(user_input)
            if not intent.supported:
                return

            plan = await self._create_plan(intent)
            step_by_id = {step.id: step for step in plan.steps}

            observation = await self._run_review_skill(step_by_id["run_review_skill"])
            observation, parsed_obs = await self._validate_review_issues(
                step_by_id["validate_review_issues"],
                observation,
            )
            await self._emit_review_issues(step_by_id["emit_review_issues"], parsed_obs)
            await self._generate_final_report(
                step_by_id["generate_final_report"],
                user_input,
                observation,
            )
        except asyncio.CancelledError:
            await self.emitter.emit(EventType.ERROR, {"message": "已被用户取消"})
        except Exception as e:
            await self.emitter.emit(EventType.ERROR, {
                "message": f"Agent 运行失败: {type(e).__name__}: {str(e)[:300]}"
            })
        finally:
            await self.emitter.emit(EventType.FINAL_ANSWER, {"content": "__DONE__"})
