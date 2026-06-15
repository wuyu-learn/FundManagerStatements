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
            for p in doc.get("paragraphs", []) or []:
                for s in p.get("sentences", []) or []:
                    sid = s.get("global_s_id")
                    if sid:
                        self._valid_sids.add(sid)

    def validate(self, observation: str) -> tuple[str, Optional[dict], dict]:
        try:
            data = json.loads(observation)
        except (json.JSONDecodeError, TypeError):
            return observation, None, {
                "fixed_short": 0,
                "hallucinated": [],
                "valid_issue_count": 0,
                "invalid_issue_count": 0,
            }
        if not isinstance(data, dict):
            return observation, None, {
                "fixed_short": 0,
                "hallucinated": [],
                "valid_issue_count": 0,
                "invalid_issue_count": 0,
            }

        issues = data.get("issues")
        if not isinstance(issues, list) or not self._valid_sids or not self.doc:
            return observation, data, {
                "fixed_short": 0,
                "hallucinated": [],
                "valid_issue_count": len(issues) if isinstance(issues, list) else 0,
                "invalid_issue_count": 0,
            }

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
            if doc_id and _SHORT_SID_RE.match(sid):
                candidate = f"{doc_id}-{sid}"
                if candidate in self._valid_sids:
                    issue["global_s_id"] = candidate
                    fixed_short += 1
                    continue
            m = _LEADING_DASH_SID_RE.match(sid)
            if doc_id and m:
                candidate = f"{doc_id}-{m.group(1)}"
                if candidate in self._valid_sids:
                    issue["global_s_id"] = candidate
                    fixed_short += 1
                    continue
            hallucinated.append(sid)
            issue["_validation_warning"] = f"global_s_id 不在文档树中: {sid}"
            issue["global_s_id"] = None

        valid_issue_count = sum(
            1 for issue in issues
            if isinstance(issue, dict) and issue.get("global_s_id")
        )
        invalid_issue_count = sum(
            1 for issue in issues
            if isinstance(issue, dict) and not issue.get("global_s_id")
        )
        stats = {
            "fixed_short": fixed_short,
            "hallucinated": hallucinated,
            "valid_issue_count": valid_issue_count,
            "invalid_issue_count": invalid_issue_count,
        }

        if hallucinated or fixed_short:
            return json.dumps(data, ensure_ascii=False), data, stats
        return observation, data, stats
