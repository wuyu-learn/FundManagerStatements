"""校验 fund-review 审核输出能否回指当前文档句子。"""

from __future__ import annotations

import json
import re
from typing import Optional


_SHORT_SID_RE = re.compile(r"^\d+-\d+$")
_LEADING_DASH_SID_RE = re.compile(r"^-+(\d+-\d+)$")


class ReviewObservationValidator:
    def __init__(self, doc: Optional[dict] = None):
        self.doc = doc
        self._valid_sids: set[str] = set()
        if doc:
            for paragraph in doc.get("paragraphs", []) or []:
                for sentence in paragraph.get("sentences", []) or []:
                    sid = sentence.get("global_s_id")
                    if sid:
                        self._valid_sids.add(sid)

    def validate(self, observation: str) -> tuple[str, Optional[dict], dict]:
        try:
            data = json.loads(observation)
        except (json.JSONDecodeError, TypeError):
            return observation, None, self._stats()

        if not isinstance(data, dict):
            return observation, None, self._stats()

        issues = data.get("issues")
        if not isinstance(issues, list) or not self._valid_sids or not self.doc:
            return observation, data, self._stats(
                valid_issue_count=len(issues) if isinstance(issues, list) else 0,
            )

        doc_id = self.doc.get("doc_id")
        hallucinated: list[str] = []
        fixed_short = 0

        for issue in issues:
            if not isinstance(issue, dict):
                continue
            sid = issue.get("global_s_id")
            if not isinstance(sid, str) or not sid:
                continue
            if sid in self._valid_sids:
                continue

            candidate = self._normalize_sid(sid, doc_id)
            if candidate and candidate in self._valid_sids:
                issue["global_s_id"] = candidate
                fixed_short += 1
                continue

            hallucinated.append(sid)
            issue["_validation_warning"] = f"global_s_id 不在文档树中: {sid}"
            issue["global_s_id"] = None

        stats = self._stats(
            fixed_short=fixed_short,
            hallucinated=hallucinated,
            valid_issue_count=sum(
                1
                for issue in issues
                if isinstance(issue, dict) and issue.get("global_s_id")
            ),
            invalid_issue_count=sum(
                1
                for issue in issues
                if isinstance(issue, dict) and not issue.get("global_s_id")
            ),
        )

        if hallucinated or fixed_short:
            return json.dumps(data, ensure_ascii=False), data, stats
        return observation, data, stats

    @staticmethod
    def _normalize_sid(sid: str, doc_id: Optional[str]) -> Optional[str]:
        if not doc_id:
            return None
        if _SHORT_SID_RE.match(sid):
            return f"{doc_id}-{sid}"
        match = _LEADING_DASH_SID_RE.match(sid)
        if match:
            return f"{doc_id}-{match.group(1)}"
        return None

    @staticmethod
    def _stats(
        fixed_short: int = 0,
        hallucinated: Optional[list[str]] = None,
        valid_issue_count: int = 0,
        invalid_issue_count: int = 0,
    ) -> dict:
        return {
            "fixed_short": fixed_short,
            "hallucinated": hallucinated or [],
            "valid_issue_count": valid_issue_count,
            "invalid_issue_count": invalid_issue_count,
        }

