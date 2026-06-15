from dataclasses import asdict, dataclass


@dataclass
class IntentResult:
    name: str
    display_name: str
    confidence: float
    reason: str
    supported: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


class IntentRecognizer:
    """Rule-first intent recognizer.

    The project currently supports one business task, but keeping this layer
    explicit makes the Agent explainable now and extensible later.
    """

    def recognize(self, raw_text: str) -> IntentResult:
        text = (raw_text or "").strip()
        if not text:
            return IntentResult(
                name="empty_input",
                display_name="空输入",
                confidence=1.0,
                reason="用户未提交可审核文本",
                supported=False,
            )

        return IntentResult(
            name="review_fund_manager_statement",
            display_name="基金经理评述审核",
            confidence=0.95,
            reason="当前系统支持基金经理评述文本审核，输入已作为待审核文本处理",
            supported=True,
        )
