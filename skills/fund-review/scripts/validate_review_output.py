#!/usr/bin/env python3
"""Validate fund-review JSON against numbered input text."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ALLOWED_CATEGORIES = {
    "保本承诺",
    "收益承诺",
    "确定性预测",
    "业绩排名",
    "推荐买入",
    "其它诱导",
    "错别字",
}
ALLOWED_SEVERITIES = {"low", "medium", "high"}
SENTENCE_RE = re.compile(r"^\[(\d+)-(\d+)\]\s*(.*)$")


def load_text(value: str) -> str:
    path = Path(value)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return value


def parse_numbered_text(numbered_text: str) -> dict[str, str]:
    sentences: dict[str, str] = {}
    for raw_line in numbered_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = SENTENCE_RE.match(line)
        if match:
            p_index, s_index, sentence = match.groups()
            sentences[f"{p_index}-{s_index}"] = sentence
    return sentences


def validate(doc_id: str, numbered_text: str, output_json: str) -> list[str]:
    errors: list[str] = []
    sentences = parse_numbered_text(numbered_text)

    try:
        payload = json.loads(output_json)
    except json.JSONDecodeError as exc:
        return [f"output is not valid JSON: {exc}"]

    if not isinstance(payload, dict):
        return ["output must be a JSON object"]

    if set(payload) - {"summary", "issues"}:
        errors.append("output has unexpected top-level fields")

    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        errors.append("summary must be a non-empty string")

    issues = payload.get("issues")
    if not isinstance(issues, list):
        errors.append("issues must be an array")
        return errors

    for index, issue in enumerate(issues):
        prefix = f"issues[{index}]"
        if not isinstance(issue, dict):
            errors.append(f"{prefix} must be an object")
            continue

        unexpected = set(issue) - {
            "global_s_id",
            "excerpt",
            "category",
            "severity",
            "comment",
        }
        if unexpected:
            errors.append(f"{prefix} has unexpected fields: {sorted(unexpected)}")

        global_s_id = issue.get("global_s_id")
        excerpt = issue.get("excerpt")
        category = issue.get("category")
        severity = issue.get("severity")
        comment = issue.get("comment")

        if not isinstance(global_s_id, str):
            errors.append(f"{prefix}.global_s_id must be a string")
            continue

        match = re.fullmatch(re.escape(doc_id) + r"-(\d+)-(\d+)", global_s_id)
        if not match:
            errors.append(f"{prefix}.global_s_id does not match doc_id and marker")
            continue

        marker = f"{match.group(1)}-{match.group(2)}"
        sentence = sentences.get(marker)
        if sentence is None:
            errors.append(f"{prefix}.global_s_id references missing marker [{marker}]")
            continue

        if not isinstance(excerpt, str) or excerpt not in sentence:
            errors.append(f"{prefix}.excerpt is not found in referenced sentence")

        if category not in ALLOWED_CATEGORIES:
            errors.append(f"{prefix}.category is not allowed: {category!r}")

        if severity not in ALLOWED_SEVERITIES:
            errors.append(f"{prefix}.severity is not allowed: {severity!r}")

        if not isinstance(comment, str) or not comment.strip():
            errors.append(f"{prefix}.comment must be a non-empty string")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc-id", required=True)
    parser.add_argument("--numbered-text", required=True, help="Text value or path")
    parser.add_argument("--output-json", required=True, help="JSON value or path")
    args = parser.parse_args()

    errors = validate(
        doc_id=args.doc_id,
        numbered_text=load_text(args.numbered_text),
        output_json=load_text(args.output_json),
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

