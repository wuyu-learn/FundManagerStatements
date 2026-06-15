"""文本深度切分：Doc → Paragraph → Sentence，每个节点都带 char 偏移以支持原文精准高亮。

关键设计：
- doc_id 由 SHA-256 hash 派生（同样输入 → 同样 ID），便于复现与去重
- 切分时严格使用 [。！？；?!;] 作为终止符；刻意不含 '.'，避免误切 1.5 / Q1.
- 列表（- * · • / 1. 1、）连续行会合并成一个段落，每行作为独立 sentence
- 所有 char_start / char_end 都是 full_text 的下标，且满足
      full_text[char_start:char_end] == s_text   # 严格相等
"""

import re
import hashlib
from typing import List, Tuple, Optional

# ----- 终止符（刻意不含半角 '.' 以避免误切小数点和英文缩写）-----
SENTENCE_TERMINATORS = "。！？；?!;"
# 匹配「连续 1 个或多个终止符」的块，方便把 "啊？？？" 当成一次终止
_TERMINATORS_RUN_RE = re.compile(rf"[{re.escape(SENTENCE_TERMINATORS)}]+")

# ----- bullet 识别：- / * / · / • / ▪ / 1. / 1、 / 1) / 1）-----
_BULLET_RE = re.compile(r"^\s*([-*·•▪]|\d+[.、)）])\s+")


def make_doc_id(text: str) -> str:
    """内容 hash → 前 8 位 → doc_<hex>。同样输入永远拿到同样 ID。"""
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"doc_{h[:8]}"


def _is_bullet_line(line: str) -> bool:
    return bool(_BULLET_RE.match(line))


def _split_paragraphs(full_text: str) -> List[Tuple[str, int, int]]:
    """
    按 \\n 切段，过滤空白段，**合并连续 bullet 行为单段**。
    返回每段的 (p_text, p_char_start, p_char_end)：
        - p_text 已 strip 首尾空白
        - 偏移量直接索引 full_text，保证 full_text[start:end] == p_text
    """
    raw_lines = full_text.split("\n")

    # 预算每行在 full_text 的起始位置（不可省，后续算偏移要用）
    line_offsets: List[int] = []
    cursor = 0
    for ln in raw_lines:
        line_offsets.append(cursor)
        cursor += len(ln) + 1  # +1 是被 split 消化掉的 '\n'

    paragraphs: List[Tuple[str, int, int]] = []
    i = 0
    n = len(raw_lines)
    while i < n:
        line = raw_lines[i]
        if not line.strip():
            i += 1
            continue

        if _is_bullet_line(line):
            # 收集连续 bullet 行（中间不允许空行/非 bullet 行）
            j = i
            while j < n and _is_bullet_line(raw_lines[j]):
                j += 1
            first_line = raw_lines[i]
            last_line = raw_lines[j - 1]
            first_leading = len(first_line) - len(first_line.lstrip())
            last_trailing = len(last_line) - len(last_line.rstrip())
            p_start = line_offsets[i] + first_leading
            p_end = line_offsets[j - 1] + len(last_line) - last_trailing
            paragraphs.append((full_text[p_start:p_end], p_start, p_end))
            i = j
        else:
            leading = len(line) - len(line.lstrip())
            trailing = len(line) - len(line.rstrip())
            p_start = line_offsets[i] + leading
            p_end = line_offsets[i] + len(line) - trailing
            paragraphs.append((full_text[p_start:p_end], p_start, p_end))
            i += 1

    return paragraphs


def _split_sentences(
    p_text: str, p_start: int, full_text: str
) -> List[Tuple[str, int, int]]:
    """
    在段落内切句。两条路径：
    - bullet 段（每行都是 bullet）：每行作为一句，即使行尾无终止符
    - 普通段：按终止符 run 切分；终止符保留在前一句末尾
    返回 (s_text, char_start, char_end)，偏移量索引 full_text。
    """
    lines = p_text.split("\n")
    non_empty_lines = [ln for ln in lines if ln.strip()]
    is_bullet_block = bool(non_empty_lines) and all(
        _is_bullet_line(ln) for ln in non_empty_lines
    )

    sentences: List[Tuple[str, int, int]] = []

    if is_bullet_block:
        cursor = 0  # 在 p_text 内的位置
        for line in lines:
            line_len = len(line)
            if line.strip():
                leading = len(line) - len(line.lstrip())
                trailing = len(line) - len(line.rstrip())
                s_start = p_start + cursor + leading
                s_end = p_start + cursor + line_len - trailing
                sentences.append((full_text[s_start:s_end], s_start, s_end))
            cursor += line_len + 1  # +1 for '\n'
        return sentences

    # 普通段：找所有终止符 run，切片
    boundaries: List[Tuple[int, int]] = []
    last_end = 0
    for m in _TERMINATORS_RUN_RE.finditer(p_text):
        end = m.end()
        boundaries.append((last_end, end))
        last_end = end
    # 末尾如果还有无终止符的残段，也算一句
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
    """
    主入口（纯切分版）：raw_text → 完整 Doc-Paragraph-Sentence 树。
    自动 strip 首尾空白；doc_id 默认按内容 hash。
    """
    full_text = raw_text.strip()
    if doc_id is None:
        doc_id = make_doc_id(full_text)

    paragraphs_out = []
    for p_index, (p_text, p_start, p_end) in enumerate(_split_paragraphs(full_text), 1):
        sentences_out = []
        for s_index, (s_text, s_start, s_end) in enumerate(
            _split_sentences(p_text, p_start, full_text), 1
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
    """
    把 build_doc_tree / process_text 返回的 doc 树扁平化为带编号的文本，喂给 LLM：

        [1-1] 第一段第一句。
        [1-2] 第一段第二句。
        [2-1] 第二段第一句。
        ...

    LLM 输出 issues 时，每条 global_s_id 必须形如 {doc_id}-{p_index}-{s_index}，
    所以这个函数不输出 doc_id 前缀（doc_id 在 system/user prompt 里另行说明）。
    """
    lines = []
    for p in doc.get("paragraphs", []):
        p_idx = p["p_index"]
        for s in p.get("sentences", []):
            lines.append(f"[{p_idx}-{s['s_index']}] {s['s_text']}")
    return "\n".join(lines)
