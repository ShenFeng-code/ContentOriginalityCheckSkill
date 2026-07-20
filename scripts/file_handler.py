#!/usr/bin/env python3
"""
文件处理模块：读取多种格式（TXT/PDF/DOCX），提取纯文本。
"""

import json
import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


SUPPORTED_EXTS = {".txt", ".md", ".pdf", ".docx", ".html", ".htm"}


def detect_format(filepath: str) -> Optional[str]:
    """检测文件格式。"""
    ext = Path(filepath).suffix.lower()
    if ext in SUPPORTED_EXTS:
        return ext
    return None


def read_file(filepath: str) -> Dict[str, str]:
    """
    读取单个文件，返回 {"name": ..., "content": ..., "format": ...}。
    失败返回 {"error": ...}。
    """
    filepath = os.path.abspath(filepath)

    if not os.path.exists(filepath):
        return {"error": f"文件不存在: {filepath}"}

    ext = detect_format(filepath)
    if ext is None:
        return {"error": f"不支持的文件格式: {ext}，支持: {', '.join(SUPPORTED_EXTS)}"}

    name = os.path.basename(filepath)

    try:
        if ext in (".txt", ".md"):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        elif ext == ".pdf":
            content = _read_pdf(filepath)
        elif ext == ".docx":
            content = _read_docx(filepath)
        elif ext in (".html", ".htm"):
            content = _read_html(filepath)
        else:
            return {"error": f"未实现读取: {ext}"}

        if not content or not content.strip():
            return {"error": f"文件内容为空: {filepath}"}

        return {"name": name, "content": content.strip(), "format": ext, "path": filepath}

    except Exception as e:
        return {"error": f"读取失败 [{name}]: {str(e)}"}


def _read_pdf(filepath: str) -> str:
    """读取 PDF 纯文本。"""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return "[错误] 缺少 PyPDF2 库，请执行: pip install PyPDF2"

    reader = PdfReader(filepath)
    texts = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            texts.append(t)
    return "\n\n".join(texts)


def _read_docx(filepath: str) -> str:
    """读取 DOCX 纯文本。"""
    try:
        from docx import Document
    except ImportError:
        return "[错误] 缺少 python-docx 库，请执行: pip install python-docx"

    doc = Document(filepath)
    texts = []
    for para in doc.paragraphs:
        if para.text.strip():
            texts.append(para.text)
    return "\n".join(texts)


def _read_html(filepath: str) -> str:
    """读取 HTML 并提取纯文本。"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # 回退：简单正则去除标签
        with open(filepath, "r", encoding="utf-8") as f:
            html = f.read()
        clean = re.compile(r'<[^>]+>')
        text = clean.sub('', html)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n").strip()


def read_directory(dirpath: str, recursive: bool = False) -> List[Dict]:
    """
    读取目录下所有支持的文件。
    """
    dirpath = os.path.abspath(dirpath)
    if not os.path.isdir(dirpath):
        return [{"error": f"路径不是目录: {dirpath}"}]

    results = []
    pattern = "*" if not recursive else "**/*"
    for p in Path(dirpath).glob(pattern):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            result = read_file(str(p))
            results.append(result)

    return results


def classify_files(paths: List[str]) -> Tuple[List[str], List[str]]:
    """
    将路径列表分类为单文件和目录。
    返回 (files, dirs)。
    """
    files, dirs = [], []
    for p in paths:
        p = os.path.abspath(p)
        if os.path.isfile(p):
            files.append(p)
        elif os.path.isdir(p):
            dirs.append(p)
    return files, dirs


# --- 主入口 ---

def main():
    import argparse
    parser = argparse.ArgumentParser(description="文件处理")
    parser.add_argument("--paths", nargs="+", required=True, help="文件或目录路径列表")
    parser.add_argument("--output", default=None, help="输出 JSON 路径")
    parser.add_argument("--recursive", action="store_true", help="递归读取子目录")
    args = parser.parse_args()

    files_list, dirs_list = classify_files(args.paths)
    results = []

    for fp in files_list:
        results.append(read_file(fp))

    for dp in dirs_list:
        dir_results = read_directory(dp, recursive=args.recursive)
        results.extend(dir_results)

    output_data = {
        "total": len(results),
        "success": sum(1 for r in results if "error" not in r),
        "failed": sum(1 for r in results if "error" in r),
        "results": results
    }

    if args.output:
        import tempfile
        tmp = args.output + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, args.output)
    else:
        print(json.dumps(output_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
