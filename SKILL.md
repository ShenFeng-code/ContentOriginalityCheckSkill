---
name: copycheck
description: >
  多模式文案查重助手。Use when the user wants to:
  (1) 检测单篇文案内部段落重复——自查/自检/是否重复/内部重复/自己查重/段落重复,
  (2) 多篇文案互相查重——互查/比对/对比/几篇文章对比/相似度/互相查重,
  (3) 与本地文档库比对查重——跟之前的比/和历史文章比对/文档库查重,
  (4) 联网检测文案是否已发布——网上有没有/网络查重/搜索引擎查重/原创检测.
  支持粘贴文本、TXT/PDF/DOCX/Markdown 文件、文件夹批量导入。
  Do NOT use for: 代码抄袭检测（那是代码查重工具的事）、图片/音视频查重、
  论文格式排版、SEO 关键词分析、文本翻译或改写（与查重不同的任务）。
---

# 文案查重助手 (CopyCheck)

多模式文案相似度检测，支持单篇自查、多篇互查、本地文档库比对、联网查重，生成 Markdown 详细报告。

## Quick Start

用户说「帮我查一下这篇文章有没有重复段落」→ 调用 `scripts/file_handler.py` 读取文件 → 调用 `scripts/checker.py --mode self` 自查 → 调用 `scripts/report_generator.py` 生成报告 → 返回报告路径。

## 查重模式

| 模式 | 用途 | 最少输入 | 触发词 |
|------|------|----------|--------|
| 自查 (`self`) | 单篇内部段落重复检测 | 1 篇文本 | 自查、内部重复、段落重复、自己查重 |
| 互查 (`cross`) | 多篇文档两两比对 | 2 篇以上 | 互查、比对、对比、互相查重、几篇比一比 |
| 文档库 (`db`) | 目标 vs 本地文档库 | 目标 + 库目录 | 跟之前比、和历史比对、文档库查重 |
| 联网 | 检测文案是否已发布到网络 | 1 篇文本 | 网上有没有、网络查重、原创检测 |

## 核心工作流

### 1. 接收输入

判断用户输入形式：
- **粘贴文本** → 直接使用
- **文件路径**（.txt/.md/.pdf/.docx/.html）→ 调用 `scripts/file_handler.py --paths <路径>` 读取
- **文件夹路径** → 调用 `scripts/file_handler.py --paths <目录> --recursive` 批量读取
- **URL**（联网模式）→ 使用 `web_fetch` 抓取

若 `file_handler.py` 失败：
- 文件不存在 → 列出目录中相似文件名，请用户确认
- 格式不支持 → 提示支持的格式列表
- 读取失败 → 报告具体错误原因

### 2. 执行查重

调用 `scripts/checker.py`：

```bash
# 单篇自查
python scripts/checker.py --mode self --input <json_file> --threshold 0.5 --output <result_json>

# 多篇互查
python scripts/checker.py --mode cross --input <json_file> --threshold 0.5 --output <result_json>

# 文档库比对
python scripts/checker.py --mode db --input <json_file> --threshold 0.5 --output <result_json>
```

输入的 JSON 文件格式：

**自查**：`{"text": "完整文本内容"}`

**互查**：`{"docs": [{"name": "A.txt", "content": "..."}, {"name": "B.txt", "content": "..."}]}`

**文档库**：`{"target": "目标文本", "db_docs": [{"name": "...", "content": "..."}]}`

阈值建议：默认 0.5。用户说「严格」→ 0.7，「宽松」→ 0.3。

若 `checker.py` 失败：
- JSON 解析失败 → 检查输入文件格式
- 文本为空 → 提示用户提供有效文本
- 依赖缺失（jieba/sklearn）→ 自动 `pip install`
- 引擎内部错误 → 报告错误信息，询问是否调整参数重试

### 3. 联网查重（可选）

当用户要求联网检测时，使用 `web_search` 搜索文案中的关键句（取前 3 句，每句 15-30 字作为搜索 query），收集匹配 URL。再将 URL 列表传给 `report_generator.py` 的 `--web_urls` 参数。

### 4. 生成报告

```bash
python scripts/report_generator.py --input <result_json> --output <report_path> --title "文案查重报告"
```

输出为 Markdown 文件，包含查重概况、相似段落对照表、相似度排名。

若 `report_generator.py` 失败：
- 输出目录不可写 → 改用工作目录
- JSON 格式错误 → 使用查重原始输出重新生成

## 错误恢复 (Error Handling)

| 错误类型 | 级别 | 处理 |
|----------|------|------|
| 文件不存在 | 可恢复 | 列出相似文件名，让用户确认 |
| 不支持的文件格式 | 可恢复 | 提示支持的格式列表 |
| 空文本 (empty input) | 可恢复 | 提示用户提供有效文本 |
| Python 依赖缺失 | 可恢复 | 自动 `pip install jieba scikit-learn PyPDF2 python-docx` |
| 文本过大 (>10MB large file) | 可恢复 | 截断处理，提示用户 |
| 特殊字符/编码问题 (special char/encoding) | 可恢复 | 尝试 UTF-8 → GBK 自动检测 |
| 磁盘空间不足 | 致命 | 报告所需空间，终止操作 |
| 权限拒绝 | 致命 | 报告路径和建议 |

## 输出规范 (Output)

- **格式**：Markdown
- **命名**：`文案查重报告-{YYYYMMDD-HHmmss}.md`
- **输出位置**：工作目录 output/
- **幂等性**：同一输入运行两次生成同名文件（覆盖，不追加）
- **内容**：禁止占位符文本（TODO/TBD/[fill in]）

## 依赖

核心依赖（自动安装）：
- `jieba` — 中文分词
- `scikit-learn` — TF-IDF 向量化
- `PyPDF2` — PDF 读取
- `python-docx` — Word 读取

## 上下文感知

- 如果用户消息中附带了文件，直接处理这些文件
- 如果刚完成自查，用户可以追加「再和文档库比对一下」继续
- 同一会话内对同一文件的多次查重，复用已读内容

## 安全

- 文件读写仅限用户指定的路径和工作目录
- 联网查重仅在用户明确要求时执行
- 不记录、不上传用户文本内容
- 临时 JSON 文件写入会话 temp 目录
