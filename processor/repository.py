"""本地文件系统仓储层 - 切分结果按 doc_id 缓存到 data/raw_docs/{doc_id}.json。

为什么不引入数据库：
- demo 本地跑，无运维负担
- doc_id 是内容 hash → 自动天然去重
- JSON 文件人类可读，方便排查与版本对比
"""

import os
import json
from typing import Optional

from .splitter import build_doc_tree, make_doc_id

# data 目录与项目根同级；本文件路径为 <root>/processor/repository.py
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(_ROOT, "data", "raw_docs")


def _ensure_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def get_doc_path(doc_id: str) -> str:
    return os.path.join(DATA_DIR, f"{doc_id}.json")


def save_doc(doc: dict) -> str:
    """写入 data/raw_docs/{doc_id}.json，返回完整路径。"""
    _ensure_dir()
    path = get_doc_path(doc["doc_id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return path


def load_doc(doc_id: str) -> Optional[dict]:
    """读 data/raw_docs/{doc_id}.json，不存在返回 None。"""
    path = get_doc_path(doc_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def process_text(raw_text: str) -> dict:
    """
    主入口（带缓存版）：
      1. 算 doc_id（基于 stripped 内容的 hash）
      2. 若本地已有 → 直接返回（节省重切开销）
      3. 否则 → 切分、保存、返回
    """
    cleaned = raw_text.strip()
    doc_id = make_doc_id(cleaned)
    cached = load_doc(doc_id)
    if cached is not None:
        return cached
    doc = build_doc_tree(cleaned, doc_id=doc_id)
    save_doc(doc)
    return doc


# ============================================================
# python -m processor.repository  ← 运行此文件即跑完整 smoke test
# ============================================================
if __name__ == "__main__":
    import sys
    import time

    # Windows cmd 默认 GBK 控制台，print emoji/UTF-8 会崩
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # 覆盖各种边界场景的样本
    sample = """2025年上半年A股市场整体以震荡上行为主，上证指数、中证800、沪深300、上证50、创业板综指等主流指数涨幅均在0%到10%之间，风格上，红利指数表现较差，为负收益。板块方面，2025年上半年申万一级行业指数中的有色金属、银行、国防军工以及传媒涨幅超过10%，在众多行业指数里表现较好，煤炭、食品饮料、房地产指数表现较差。

重点配置如下：
- 银行（占比 30%）
- 国防军工（占比 25%）
- 有色金属（占比 20%）

展望下半年，本基金将继续关注高景气度板块。GDP增长1.5%是基础假设，CPI预计在2.3%左右。真的吗？？？我们认为答案是肯定的。"""

    print("=" * 60)
    print("第一次调用 process_text（应该实际切分并落盘）")
    print("=" * 60)
    t0 = time.time()
    doc = process_text(sample)
    t1 = (time.time() - t0) * 1000

    print(json.dumps(doc, ensure_ascii=False, indent=2))
    print()
    print(f"耗时: {t1:.1f}ms")
    print(f"doc_id: {doc['doc_id']}")
    print(f"段落数: {len(doc['paragraphs'])}")
    print(f"总句数: {sum(len(p['sentences']) for p in doc['paragraphs'])}")
    print(f"持久化路径: {get_doc_path(doc['doc_id'])}")

    # ---- 关键校验：每句的偏移量必须能严格切回 s_text ----
    print()
    print("-" * 60)
    print("校验 char_start / char_end 与 s_text 是否完全一致")
    print("-" * 60)
    bad = 0
    for p in doc["paragraphs"]:
        if doc["full_text"][p["p_char_start"]:p["p_char_end"]] != p["p_text"]:
            bad += 1
            print(f"⚠️  段落偏移不一致: p_index={p['p_index']}")
        for s in p["sentences"]:
            sliced = doc["full_text"][s["char_start"]:s["char_end"]]
            if sliced != s["s_text"]:
                bad += 1
                print(f"⚠️  句子偏移不一致: {s['global_s_id']}")
                print(f"    s_text: {s['s_text']!r}")
                print(f"    sliced: {sliced!r}")
    if bad == 0:
        print("✅ 所有段落 + 所有句子的偏移量都能严格切回原文")
    else:
        print(f"❌ 共 {bad} 处偏移不一致")

    # ---- 缓存验证：第二次调用应该走 load_doc，几乎不耗时 ----
    print()
    print("-" * 60)
    print("第二次调用 process_text（同样输入，应命中缓存）")
    print("-" * 60)
    t0 = time.time()
    doc2 = process_text(sample)
    t2 = (time.time() - t0) * 1000
    print(f"耗时: {t2:.2f}ms（命中缓存应远小于第一次的 {t1:.1f}ms）")
    print(f"doc_id 是否一致: {doc['doc_id'] == doc2['doc_id']}")
    print(f"结构是否完全一致: {doc == doc2}")
