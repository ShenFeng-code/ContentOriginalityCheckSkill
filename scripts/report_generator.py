#!/usr/bin/env python3
"""
报告生成器：将查重 JSON 结果渲染为 Markdown 报告。
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, Any


def generate_markdown(check_result: Dict[str, Any], title: str = "文案查重报告") -> str:
    """
    将查重结果渲染为 Markdown 报告。
    """
    lines = []
    lines.append(f"# {title}")
    lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    mode = check_result.get("mode", "")

    if mode == "self_check":
        lines.extend(_self_check_report(check_result))
    elif mode == "cross_check":
        lines.extend(_cross_check_report(check_result))
    elif mode == "db_check":
        lines.extend(_db_check_report(check_result))
    else:
        lines.append(f"未知查重模式: {mode}")

    return "\n".join(lines)


def _self_check_report(result: Dict) -> list:
    lines = []
    lines.append("## 单篇自查")
    lines.append("")
    lines.append(f"- 总段落数: {result.get('total_paragraphs', 0)}")
    lines.append(f"- 相似段落对: {len(result.get('duplicate_pairs', []))}")
    lines.append(f"- 内部重复率: {result.get('overall_ratio', 0) * 100:.1f}%")
    lines.append("")

    pairs = result.get("duplicate_pairs", [])
    if not pairs:
        lines.append("**未发现相似段落。**")
        return lines

    lines.append("### 相似段落对照")
    lines.append("")
    lines.append("| # | 段落 A | 段落 B | 相似度 |")
    lines.append("|---|---|---|---|")
    for p in pairs:
        lines.append(f"| {p['paragraph_a']} | {p['text_a'][:60]}... | {p['text_b'][:60]}... | {p['similarity']*100:.1f}% |")
    lines.append("")

    return lines


def _cross_check_report(result: Dict) -> list:
    lines = []
    lines.append("## 多篇互查")
    lines.append("")
    lines.append(f"- 文档总数: {result.get('total_docs', 0)}")
    lines.append(f"- 相似文档对: {len(result.get('pairs', []))}")
    lines.append(f"- 重复率: {result.get('overall_ratio', 0) * 100:.1f}%")
    lines.append("")

    pairs = result.get("pairs", [])
    if not pairs:
        lines.append("**未发现相似文档。**")
        return lines

    lines.append("### 文档相似度矩阵")
    lines.append("")

    for pair in pairs:
        lines.append(f"#### {pair['doc_a']} ↔ {pair['doc_b']}")
        lines.append(f"> 整体相似度: **{pair['overall_similarity']*100:.1f}%**")
        lines.append("")
        top = pair.get("top_paragraph_matches", [])
        if top:
            lines.append("| 段落 A | 段落 B | 相似度 | 文本片段 |")
            lines.append("|---|---|---|---|")
            for m in top[:5]:
                snippet = m.get('text_a', '')[:50]
                lines.append(
                    f"| P{m['paragraph_a_index']} | P{m['paragraph_b_index']} | "
                    f"{m['similarity']*100:.1f}% | {snippet}... |"
                )
        lines.append("")

    return lines


def _db_check_report(result: Dict) -> list:
    lines = []
    lines.append("## 文档库比对")
    lines.append("")
    lines.append(f"- 目标段落数: {result.get('target_paragraphs', 0)}")
    lines.append(f"- 比对文档数: {result.get('db_docs_count', 0)}")
    lines.append("")

    results = result.get("results", [])
    if not results:
        lines.append("**无匹配结果。**")
        return lines

    lines.append("### 比对结果")
    lines.append("")
    lines.append("| 文档库文档 | 匹配段落数 | 重合率 |")
    lines.append("|---|---|---|")
    for r in results:
        lines.append(f"| {r['db_doc']} | {r['match_count']} | {r['similarity_ratio']*100:.1f}% |")
    lines.append("")

    # 展示最高匹配文档的详细段落对照
    top = results[0]
    lines.append(f"### 最高匹配: {top['db_doc']}")
    lines.append("")
    top_matches = top.get("top_matches", [])
    if top_matches:
        lines.append("| 目标段落 | 库段落 | 相似度 | 文本片段 |")
        lines.append("|---|---|---|---|")
        for m in top_matches[:10]:
            snippet = m.get('text_snippet', '')[:60]
            lines.append(
                f"| {m['target_para']} | {m['db_para']} | "
                f"{m['similarity']*100:.1f}% | {snippet} |"
            )
    lines.append("")

    return lines


def generate_web_report(check_result: Dict[str, Any], urls: list = None) -> str:
    """附加联网查重结果。"""
    lines = []
    if urls:
        lines.append("## 联网查重")
        lines.append("")
        lines.append(f"检测到 {len(urls)} 个可能来源:")
        lines.append("")
        for url in urls:
            lines.append(f"- [{url}]({url})")
        lines.append("")
    else:
        lines.append("## 联网查重")
        lines.append("")
        lines.append("未发现网络匹配结果。")
        lines.append("")
    return "\n".join(lines)


# --- 主入口 ---

def main():
    import argparse
    parser = argparse.ArgumentParser(description="报告生成")
    parser.add_argument("--input", required=True, help="查重结果 JSON 文件路径")
    parser.add_argument("--output", required=True, help="输出 Markdown 路径")
    parser.add_argument("--title", default="文案查重报告", help="报告标题")
    parser.add_argument("--web_urls", nargs="*", help="联网查重 URL 列表")
    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(json.dumps({"status": "error", "reason": f"文件不存在: {args.input}"}))
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "error", "reason": f"JSON 解析失败: {str(e)}"}))
        sys.exit(2)

    md = generate_markdown(data, args.title)

    if args.web_urls:
        md += "\n" + generate_web_report(data, args.web_urls)

    # 原子写入
    tmp = args.output + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(md)
    os.replace(tmp, args.output)

    print(json.dumps({
        "status": "ok",
        "output": os.path.abspath(args.output),
        "size": len(md.encode("utf-8"))
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
