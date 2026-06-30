"""
baseline_search.py — BM25 关键词搜索 over baseline/ 文件

给 Ombre Brain 提供 /api/archive-search 端点，替代独立的 vector-memory server。
纯 BM25 + jieba 分词，不需要 sentence-transformers 等重型模型。
"""
import os
import re
import logging
from pathlib import Path

logger = logging.getLogger("ombre_brain.baseline_search")

try:
    import jieba
    from rank_bm25 import BM25Okapi
except ImportError:
    jieba = None
    BM25Okapi = None
    logger.warning("jieba/rank_bm25 未安装，baseline_search 不可用")

CYBERBOSS = os.path.expanduser("~/.cyberboss")
BASELINE_DIR = os.path.join(CYBERBOSS, "baseline")


def _list_md_files(root_dir):
    """递归收集所有 .md 文件路径。"""
    result = []
    if not os.path.isdir(root_dir):
        return result
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            if fn.endswith(".md"):
                result.append(os.path.join(dirpath, fn))
    return sorted(result)


def _chunk_md(filepath, max_chars=800):
    """将 .md 文件按标题拆成段落块。跳过 YAML frontmatter。"""
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    # Strip YAML frontmatter
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].strip()
    rel_path = os.path.relpath(filepath, BASELINE_DIR).replace("\\", "/")
    lines = text.split("\n")
    chunks = []
    current_lines = []
    current_heading = rel_path
    for line in lines:
        hm = re.match(r"^(#{1,3})\s+(.+)$", line)
        if hm:
            if current_lines:
                body = "\n".join(current_lines).strip()
                if body:
                    chunks.append({"path": rel_path, "heading": current_heading, "text": body})
            current_heading = hm.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        body = "\n".join(current_lines).strip()
        if body:
            chunks.append({"path": rel_path, "heading": current_heading, "text": body})
    # Merge small chunks
    merged = []
    for c in chunks:
        if merged and len(merged[-1]["text"]) < max_chars and len(c["text"]) < 200:
            merged[-1]["text"] += "\n" + c["text"]
        else:
            merged.append(c)
    return merged


class BaselineSearch:
    """BM25 搜索引擎，定期从 baseline/ 重建索引。"""

    def __init__(self, baseline_dir=None):
        self.baseline_dir = baseline_dir or BASELINE_DIR
        self.chunks = []
        self.tokenized = []
        self.bm25 = None

    def rebuild_index(self):
        """扫描 baseline/ 文件，构建 BM25 索引。"""
        if jieba is None or BM25Okapi is None:
            logger.warning("jieba/rank_bm25 不可用，跳过索引重建")
            return
        files = _list_md_files(self.baseline_dir)
        all_chunks = []
        for fp in files:
            all_chunks.extend(_chunk_md(fp))
        if not all_chunks:
            self.chunks = []
            self.tokenized = []
            self.bm25 = None
            logger.info("[baseline_search] 无文件可索引")
            return
        self.chunks = all_chunks
        self.tokenized = [list(jieba.cut(c["text"])) for c in all_chunks]
        self.bm25 = BM25Okapi(self.tokenized)
        logger.info(f"[baseline_search] 索引完成: {len(files)} 文件, {len(all_chunks)} 段落")

    def search(self, query, limit=5):
        """关键词搜索，返回兼容 vector-memory 格式的结果 [{summary, timestamp, sim, role}, ...]"""
        if not self.bm25 or not query:
            return []
        tokens = list(jieba.cut(query))
        scores = self.bm25.get_scores(tokens)
        scored = [(i, scores[i]) for i in range(len(scores)) if scores[i] > 0]
        scored.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in scored[:limit]:
            c = self.chunks[idx]
            results.append({
                "summary": c["text"].replace("\n", " ").strip()[:80],
                "timestamp": c["path"],
                "sim": round(float(score), 2),
                "role": "user",
            })
        return results
