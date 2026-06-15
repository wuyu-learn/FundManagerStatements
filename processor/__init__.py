"""文档处理 - 把原始文本切分为 Doc → Paragraph → Sentence 三层结构，并提供本地缓存。

对外的三个主入口：
- splitter.build_doc_tree(raw_text)         —— 纯切分，返回 dict
- splitter.format_to_numbered_text(doc)     —— 扁平化为带 [p-s] 编号的文本（给 LLM）
- repository.process_text(raw_text)         —— 切分 + 持久化 + 读缓存
"""

from .splitter import build_doc_tree, make_doc_id, format_to_numbered_text
from .repository import process_text, save_doc, load_doc, get_doc_path, DATA_DIR

__all__ = [
    "build_doc_tree",
    "make_doc_id",
    "format_to_numbered_text",
    "process_text",
    "save_doc",
    "load_doc",
    "get_doc_path",
    "DATA_DIR",
]
