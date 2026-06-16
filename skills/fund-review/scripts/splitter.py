"""基金评述文本切分：Doc → Paragraph → Sentence。

这是 fund-review 技能包的预处理能力：
- 将原始评述切分为段落和句子
- 为每个句子生成稳定的 global_s_id
- 保留 char_start / char_end，供前端做原文高亮
- 输出带 [p-s] 标记的 numbered_text，供审核模型使用
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional


SENTENCE_TERMINATORS = "。！？；?!;"
_TERMINATORS_RUN_RE = re.compile(rf"[{re.escape(SENTENCE_TERMINATORS)}]+")
_BULLET_RE = re.compile(r"^\s*([-*·•▪]|\d+[.、)）])\s+")


def make_doc_id(text: str) -> str:
    """内容 hash → 前 8 位 → doc_<hex>。同样输入永远拿到同样 ID。"""
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"doc_{h[:8]}"


def _is_bullet_line(line: str) -> bool:
    return bool(_BULLET_RE.match(line))


def _split_paragraphs(full_text: str) -> list[tuple[str, int, int]]:
    """按空行切段，并将连续 bullet 行合并为同一段。"""
    raw_lines = full_text.split("\n")
    line_offsets: list[int] = []
    cursor = 0
    for line in raw_lines:
        line_offsets.append(cursor)
        cursor += len(line) + 1

    paragraphs: list[tuple[str, int, int]] = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        if not line.strip():
            i += 1
            continue

        if _is_bullet_line(line):
            j = i
            while j < len(raw_lines) and _is_bullet_line(raw_lines[j]):
                j += 1
            first_line = raw_lines[i]
            last_line = raw_lines[j - 1]
            p_start = line_offsets[i] + len(first_line) - len(first_line.lstrip())
            p_end = line_offsets[j - 1] + len(last_line.rstrip())
            paragraphs.append((full_text[p_start:p_end], p_start, p_end))
            i = j
            continue

        leading = len(line) - len(line.lstrip())
        trailing = len(line) - len(line.rstrip())
        p_start = line_offsets[i] + leading
        p_end = line_offsets[i] + len(line) - trailing
        paragraphs.append((full_text[p_start:p_end], p_start, p_end))
        i += 1

    return paragraphs


def _split_sentences(
    p_text: str,
    p_start: int,
    full_text: str,
) -> list[tuple[str, int, int]]:
    """在段落内切句；bullet 段按行切，普通段按中文语义终止符切。"""
    lines = p_text.split("\n")
    non_empty_lines = [line for line in lines if line.strip()]
    is_bullet_block = bool(non_empty_lines) and all(
        _is_bullet_line(line) for line in non_empty_lines
    )

    sentences: list[tuple[str, int, int]] = []

    if is_bullet_block:
        cursor = 0
        for line in lines:
            line_len = len(line)
            if line.strip():
                leading = len(line) - len(line.lstrip())
                trailing = len(line) - len(line.rstrip())
                s_start = p_start + cursor + leading
                s_end = p_start + cursor + line_len - trailing
                sentences.append((full_text[s_start:s_end], s_start, s_end))
            cursor += line_len + 1
        return sentences

    boundaries: list[tuple[int, int]] = []
    last_end = 0
    for match in _TERMINATORS_RUN_RE.finditer(p_text):
        end = match.end()
        boundaries.append((last_end, end))
        last_end = end
    if last_end < len(p_text):
        boundaries.append((last_end, len(p_text)))

    for local_start, local_end in boundaries:
        piece = p_text[local_start:local_end]
        if not piece.strip():
            continue
        leading = len(piece) - len(piece.lstrip())
        trailing = len(piece) - len(piece.rstrip())
        s_start = p_start + local_start + leading
        s_end = p_start + local_end - trailing
        sentences.append((full_text[s_start:s_end], s_start, s_end))

    return sentences


def build_doc_tree(raw_text: str, doc_id: Optional[str] = None) -> dict:
    """原始文本 → Doc-Paragraph-Sentence 树。"""
    full_text = raw_text.strip()
    if doc_id is None:
        doc_id = make_doc_id(full_text)

    paragraphs_out = []
    for p_index, (p_text, p_start, p_end) in enumerate(
        _split_paragraphs(full_text),
        1,
    ):
        sentences_out = []
        for s_index, (s_text, s_start, s_end) in enumerate(
            _split_sentences(p_text, p_start, full_text),
            1,
        ):
            sentences_out.append({
                "s_index": s_index,
                "global_s_id": f"{doc_id}-{p_index}-{s_index}",
                "s_text": s_text,
                "char_start": s_start,
                "char_end": s_end,
            })
        paragraphs_out.append({
            "p_index": p_index,
            "p_text": p_text,
            "p_char_start": p_start,
            "p_char_end": p_end,
            "sentences": sentences_out,
        })

    return {
        "doc_id": doc_id,
        "full_text": full_text,
        "paragraphs": paragraphs_out,
    }


def format_to_numbered_text(doc: dict) -> str:
    """Doc 树 → 带 [p-s] 编号的扁平文本。"""
    lines = []
    for paragraph in doc.get("paragraphs", []):
        p_index = paragraph["p_index"]
        for sentence in paragraph.get("sentences", []):
            lines.append(f"[{p_index}-{sentence['s_index']}] {sentence['s_text']}")
    return "\n".join(lines)

