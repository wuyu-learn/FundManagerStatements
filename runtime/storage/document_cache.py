"""本地文档缓存：将 fund-review 切分结果保存到 data/raw_docs/{doc_id}.json。"""

import json
import os
from typing import Optional

from runtime.skills.assets import load_skill_script


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(ROOT_DIR, "data", "raw_docs")
_splitter = load_skill_script("fund-review", "splitter.py")


def _ensure_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def get_doc_path(doc_id: str) -> str:
    return os.path.join(DATA_DIR, f"{doc_id}.json")


def save_doc(doc: dict) -> str:
    _ensure_dir()
    path = get_doc_path(doc["doc_id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return path


def load_doc(doc_id: str) -> Optional[dict]:
    path = get_doc_path(doc_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def process_text(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    doc_id = _splitter.make_doc_id(cleaned)
    cached = load_doc(doc_id)
    if cached is not None:
        return cached
    doc = _splitter.build_doc_tree(cleaned, doc_id=doc_id)
    save_doc(doc)
    return doc

