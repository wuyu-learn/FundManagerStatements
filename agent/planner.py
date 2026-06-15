from dataclasses import asdict, dataclass

from .intents import IntentResult


@dataclass
class PlanStep:
    id: str
    name: str
    executor: str
    purpose: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TaskPlan:
    intent: str
    template_id: str
    steps: list[PlanStep]

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "template_id": self.template_id,
            "steps": [step.to_dict() for step in self.steps],
        }


class TaskPlanner:
    def create_plan(self, intent: IntentResult) -> TaskPlan:
        if intent.name != "review_fund_manager_statement" or not intent.supported:
            raise ValueError(f"Unsupported intent: {intent.name}")

        return TaskPlan(
            intent=intent.name,
            template_id="standard_review_v1",
            steps=[
                PlanStep(
                    id="run_review_skill",
                    name="执行结构化审核",
                    executor="Review Skill",
                    purpose="识别单句合规风险与文字错误",
                ),
                PlanStep(
                    id="validate_review_issues",
                    name="校验问题定位",
                    executor="Agent Validator",
                    purpose="确认每条 issue 能映射到当前文档句子",
                ),
                PlanStep(
                    id="emit_review_issues",
                    name="推送审核反馈",
                    executor="Event Stream",
                    purpose="将结构化 issues 推送给前端审核反馈栏",
                ),
                PlanStep(
                    id="generate_final_report",
                    name="生成完整审核报告",
                    executor="LLM",
                    purpose="基于 Review 结果生成宏观合规定性综述",
                ),
            ],
        )
