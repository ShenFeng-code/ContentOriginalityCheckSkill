#!/usr/bin/env python3
"""
核心查重引擎：文本相似度计算、段落级比对、重复片段标注。
支持单篇自查、多篇互查、本地文档库比对。
"""

import json
import os
import re
import sys
import hashlib
from collections import defaultdict
from difflib import SequenceMatcher
from typing import List, Dict, Tuple, Optional, Any


# --- 分词与预处理 ---

def _load_jieba():
    """惰性加载 jieba，附带依赖检测。"""
    try:
        import jieba
        jieba.setLogLevel(20)  # 静默
        return jieba
    except ImportError:
        return None


def tokenize(text: str, granularity: str = "sentence") -> List[str]:
    """
    按句子或段落切分文本。
    granularity: "sentence" | "paragraph"
    """
    if granularity == "paragraph":
        parts = re.split(r'\n\s*\n', text.strip())
        return [p.strip() for p in parts if len(p.strip()) >= 10]
    else:
        parts = re.split(r'[。！？.!?\n]+', text)
        parts = [p.strip() for p in parts if len(p.strip()) >= 5]
        return parts


def _ngram_hash(text: str, n: int = 3) -> List[str]:
    """生成 n-gram hash 签名，用于快速粗筛。"""
    tokens = list(text)
    hashes = []
    for i in range(len(tokens) - n + 1):
        gram = ''.join(tokens[i:i+n])
        hashes.append(hashlib.md5(gram.encode('utf-8')).hexdigest()[:8])
    return hashes


# --- 相似度计算 ---

def cosine_similarity_tfidf(docs: List[str]) -> np.ndarray:
    """TF-IDF 余弦相似度矩阵。依赖 sklearn。"""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
    except ImportError:
        return None

    vectorizer = TfidfVectorizer(
        token_pattern=r'(?u)\b\w+\b',
        max_features=5000,
        stop_words=None
    )
    try:
        tfidf = vectorizer.fit_transform(docs)
        sim = cosine_similarity(tfidf)
        return sim
    except Exception:
        return None


def jaccard_similarity(a: List[str], b: List[str]) -> float:
    """Jaccard 相似度（基于 n-gram hash 集）。"""
    set_a, set_b = set(a), set(b)
    if not set_a and not set_b:
        return 1.0
    return len(set_a & set_b) / len(set_a | set_b)


def sequence_similarity(a: str, b: str) -> float:
    """基于 SequenceMatcher 的文本相似度。"""
    return SequenceMatcher(None, a, b).ratio()


# --- 单篇自查 ---

def self_check(text: str, threshold: float = 0.6) -> Dict[str, Any]:
    """
    检测单篇文案内部段落重复。
    返回重复段落对及其相似度。
    """
    paragraphs = tokenize(text, granularity="paragraph")
    n = len(paragraphs)

    if n < 2:
        return {
            "mode": "self_check",
            "total_paragraphs": n,
            "duplicate_pairs": [],
            "overall_ratio": 0.0,
            "summary": "文本段落不足 2 段，无需查重。"
        }

    pairs = []
    duplicate_count = 0

    for i in range(n):
        for j in range(i + 1, n):
            sim = sequence_similarity(paragraphs[i], paragraphs[j])
            if sim >= threshold:
                pairs.append({
                    "paragraph_a": i + 1,
                    "paragraph_b": j + 1,
                    "similarity": round(sim, 4),
                    "text_a": paragraphs[i][:200],
                    "text_b": paragraphs[j][:200]
                })
                duplicate_count += 1

    overall = duplicate_count / (n * (n - 1) / 2) if n > 1 else 0.0

    return {
        "mode": "self_check",
        "total_paragraphs": n,
        "duplicate_pairs": pairs,
        "overall_ratio": round(overall, 4),
        "summary": (
            f"共 {n} 段，发现 {len(pairs)} 对相似段落，"
            f"内部重复率 {overall*100:.1f}%"
        )
    }


# --- 多篇互查 ---

def cross_check(docs: List[Dict[str, str]], threshold: float = 0.5) -> Dict[str, Any]:
    """
    多篇文档互查。
    docs: [{"name": "文件名", "content": "全文内容"}, ...]
    """
    n = len(docs)
    if n < 2:
        return {
            "mode": "cross_check",
            "total_docs": n,
            "pairs": [],
            "overall_ratio": 0.0,
            "summary": "文档数量不足 2 篇，无法互查。"
        }

    contents = [d["content"] for d in docs]

    # 尝试 TF-IDF
    sim_matrix = cosine_similarity_tfidf(contents)

    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            if sim_matrix is not None:
                doc_sim = float(sim_matrix[i][j])
            else:
                # 回退到段落级比对平均
                para_i = tokenize(contents[i], "paragraph")
                para_j = tokenize(contents[j], "paragraph")
                scores = []
                for pi in para_i:
                    for pj in para_j:
                        scores.append(sequence_similarity(pi, pj))
                doc_sim = sum(scores) / len(scores) if scores else 0.0

            if doc_sim >= threshold:
                # 找出最相似的段落对
                para_i = tokenize(contents[i], "paragraph")
                para_j = tokenize(contents[j], "paragraph")
                top_pairs = _top_paragraph_pairs(para_i, para_j, topk=3)
                pairs.append({
                    "doc_a": docs[i]["name"],
                    "doc_b": docs[j]["name"],
                    "overall_similarity": round(doc_sim, 4),
                    "top_paragraph_matches": top_pairs
                })

    duplicate_pairs_count = len(pairs)
    overall = duplicate_pairs_count / (n * (n - 1) / 2) if n > 1 else 0.0

    return {
        "mode": "cross_check",
        "total_docs": n,
        "pairs": pairs,
        "overall_ratio": round(overall, 4),
        "summary": (
            f"共 {n} 篇文档，发现 {len(pairs)} 对相似文档，"
            f"重复率 {overall*100:.1f}%"
        )
    }


def _top_paragraph_pairs(pa: List[str], pb: List[str], topk: int = 3) -> List[Dict]:
    """找出两篇文档中最相似的 topk 段落对。"""
    scores = []
    for i, pi in enumerate(pa):
        for j, pj in enumerate(pb):
            sim = sequence_similarity(pi, pj)
            if sim >= 0.5:
                scores.append((sim, i, j, pi[:200], pj[:200]))
    scores.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "paragraph_a_index": i + 1,
            "paragraph_b_index": j + 1,
            "similarity": round(sim, 4),
            "text_a": ta,
            "text_b": tb
        }
        for sim, i, j, ta, tb in scores[:topk]
    ]


# --- 文档库比对 ---

def db_check(target_text: str, db_docs: List[Dict[str, str]], threshold: float = 0.5) -> Dict[str, Any]:
    """
    将目标文本与本地文档库逐一比对。
    """
    results = []
    target_paras = tokenize(target_text, "paragraph")

    for doc in db_docs:
        doc_paras = tokenize(doc["content"], "paragraph")
        match_count = 0
        top_matches = []

        for i, tp in enumerate(target_paras):
            for j, dp in enumerate(doc_paras):
                sim = sequence_similarity(tp, dp)
                if sim >= threshold:
                    match_count += 1
                    top_matches.append({
                        "target_para": i + 1,
                        "db_para": j + 1,
                        "similarity": round(sim, 4),
                        "text_snippet": tp[:150]
                    })

        top_matches.sort(key=lambda x: x["similarity"], reverse=True)
        top_matches = top_matches[:10]

        ratio = match_count / max(len(target_paras), 1)
        results.append({
            "db_doc": doc["name"],
            "match_count": match_count,
            "similarity_ratio": round(ratio, 4),
            "top_matches": top_matches
        })

    results.sort(key=lambda x: x["similarity_ratio"], reverse=True)

    return {
        "mode": "db_check",
        "target_paragraphs": len(target_paras),
        "db_docs_count": len(db_docs),
        "results": results,
        "summary": (
            f"与 {len(db_docs)} 篇文档比对完成，"
            f"最相似文档重合率 {results[0]['similarity_ratio']*100:.1f}%"
            if results else "无匹配结果"
        )
    }


# --- 主入口（JSON 输出，符合 polyglot interop 标准）---

def main():
    import argparse
    parser = argparse.ArgumentParser(description="文案查重引擎")
    parser.add_argument("--mode", required=True,
                        choices=["self", "cross", "db"])
    parser.add_argument("--input", required=True,
                        help="JSON 输入文件路径")
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="相似度阈值 (0-1)")
    parser.add_argument("--output", default=None,
                        help="输出 JSON 路径，默认 stdout")
    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        result = {"status": "error", "reason": f"输入文件不存在: {args.input}", "recoverable": True}
        _output(result, args.output)
        sys.exit(2)
    except json.JSONDecodeError as e:
        result = {"status": "error", "reason": f"JSON 解析失败: {str(e)}", "recoverable": True}
        _output(result, args.output)
        sys.exit(2)

    try:
        if args.mode == "self":
            text = data.get("text", "")
            if not text.strip():
                result = {"status": "error", "reason": "输入文本为空", "recoverable": True}
                _output(result, args.output)
                sys.exit(2)
            result = self_check(text, args.threshold)

        elif args.mode == "cross":
            docs = data.get("docs", [])
            if len(docs) < 2:
                result = {"status": "error", "reason": "至少需要 2 篇文档进行互查", "recoverable": True}
                _output(result, args.output)
                sys.exit(2)
            for doc in docs:
                if "name" not in doc or "content" not in doc:
                    result = {"status": "error", "reason": "每篇文档需包含 name 和 content 字段", "recoverable": True}
                    _output(result, args.output)
                    sys.exit(2)
            result = cross_check(docs, args.threshold)

        elif args.mode == "db":
            target = data.get("target", "")
            db_docs = data.get("db_docs", [])
            if not target.strip():
                result = {"status": "error", "reason": "目标文本为空", "recoverable": True}
                _output(result, args.output)
                sys.exit(2)
            if not db_docs:
                result = {"status": "error", "reason": "文档库为空", "recoverable": True}
                _output(result, args.output)
                sys.exit(2)
            result = db_check(target, db_docs, args.threshold)

        result["status"] = "ok"
        _output(result, args.output)
    except Exception as e:
        result = {"status": "error", "reason": f"引擎内部错误: {str(e)}", "recoverable": False}
        _output(result, args.output)
        sys.exit(1)


def _output(data: dict, path: Optional[str]):
    if path:
        import tempfile
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)  # 原子写入
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
