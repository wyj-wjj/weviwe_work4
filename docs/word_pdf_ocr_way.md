# Word/PDF 导入解析与 OCR 兜底方案

> 日期：2026-06-30
> 目标：管理员上传 Word/PDF 后，系统解析并填入“最新必读、核心基础话术、标准化话术”对应草稿字段，管理员人工检查后再发布。

## 1. 背景与目标

管理员维护内容时，经常会拿到格式不统一的 Word、PDF、扫描件、截图型文档、表格文档或多来源拼接文档。如果系统只做简单文本提取，真实使用时很容易出现解析不完整、表格错乱、扫描页空白、字段归类错误等问题，管理员仍然会回到手工复制粘贴。

本功能第一版要解决的是“降低管理员创建草稿的录入成本”，不是替管理员自动发布官方内容。因此导入结果只填入新建内容表单或保存为草稿，不自动发布，不进入员工端，不进入 AI 检索索引。管理员必须人工检查并按现有发布流程发布后，内容才对员工可见。

## 2. 功能范围

### 2.1 本期目标

- 支持管理员上传 `.docx` 和 `.pdf`。
- 管理员先选择内容类型：`最新必读`、`核心基础话术`、`标准化话术`。
- 上传解析后始终返回一份单条草稿建议，并可返回拆解候选草稿列表。
- 支持 PDF 的“快速解析”和“增强解析”两种模式。
- 对格式混乱、扫描页、截图页、表格页提供 OCR 兜底。
- 使用大模型做字段结构化整理，但默认不改写官方话术原文。
- 返回 `warnings`、`parse_method`、逐页解析信息，让管理员知道哪些地方需要重点核对。
- 解析接口必须只有管理员可用。
- 解析失败、文件过大、文件类型不支持、模型超时等情况必须有明确错误提示。

### 2.2 非目标

- 不自动发布内容。
- 不在导入时写入 Milvus 或生成向量索引。
- 不支持老版 `.doc` 文件；管理员需要先另存为 `.docx` 后上传。
- 不自动强制把一个文件拆成多条草稿；拆解结果只作为候选，管理员确认后才保存。
- 不默认让大模型重写正文、推荐说法、禁用说法。
- 不把上传原文件长期保存为正式附件库。
- 不引入独立文档管理系统。

后续可以在文档模板稳定后，再扩展“一个文件拆多条草稿”和“批量导入确认页”。

## 3. 总体工作流

管理员操作流程：

1. 进入后台“新建内容”页。
2. 选择内容类型：
   - 核心基础话术：`base_script`
   - 标准化话术：`standard_script`
   - 最新必读：`must_read`
3. 选择解析模式：
   - 快速解析：适合文字型 PDF 和普通 DOCX，速度快、成本低。
   - 增强解析：适合扫描 PDF、截图多、表格多、格式混乱的文档，速度慢、成本高。
4. 上传 `.docx` 或 `.pdf`。
5. 点击“解析并填入表单”。
6. 后端返回 `single_draft` 和可选的 `split_suggestions`。
7. 前端默认展示单条草稿；如果文档较大或主题较多，管理员可以切到“拆解候选”查看。
8. 管理员选择“使用单条草稿”，或从拆解候选中勾选若干条、删除、编辑、合并后保存。
9. 管理员检查、修改字段。
10. 管理员点击“保存草稿”或“保存选中为草稿”。
11. 管理员在内容列表按现有发布流程发布。

系统处理流程：

```text
上传文件
  -> 文件校验
  -> 本地解析 DOCX/PDF
  -> 必要时或增强模式下调用 OCR
  -> 对多路解析结果逐页评分、择优或融合
  -> qwen-plus 结构化整理成单条草稿
  -> qwen-plus 生成可选拆解候选
  -> 返回单条草稿、拆解候选和解析警告
```

## 4. 模型与能力分工

| 能力 | 模型/接口 | 本期是否使用 | 用途 |
| --- | --- | --- | --- |
| OCR | `qwen-vl-ocr-2025-11-20` | 使用 | 扫描页、截图页、图片型 PDF、DOCX 内嵌图片的文字识别 |
| 文本结构化 | `qwen-plus` | 使用 | 将原始文本整理成三类内容对应字段 JSON |
| 普通视觉理解 | `qwen3.5-flash` | 暂不主用 | 后续可用于复杂图片理解兜底 |
| 文本向量 | `text-embedding-v4` | 导入时不用 | 内容发布后，现有索引同步流程继续使用 |
| 多模态向量 | `qwen3-vl-embedding` | 第一版不用 | 适合图文跨模态检索，不适合草稿导入主流程 |

重要原则：

- OCR 负责“看清文字”。
- `qwen-plus` 负责“归类字段”。
- 模型不得凭空补充业务结论。
- 正文和官方话术默认尽量保留原文。
- 摘要可以生成，但必须作为管理员可修改的建议摘要。

## 5. 后端接口设计

新增管理员接口：

```text
POST /api/admin/content-import/parse
Content-Type: multipart/form-data
```

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `content_type` | string | 是 | `base_script`、`standard_script`、`must_read` |
| `parse_mode` | string | 否 | `fast` 或 `enhanced`，默认 `fast` |
| `force_ocr` | boolean | 否 | 是否强制 OCR，默认 `false` |
| `file` | file | 是 | `.docx` 或 `.pdf` |

建议限制：

- 文件大小上限：第一版建议 20MB。
- PDF 页数上限：第一版建议 80 页。
- OCR 页数上限：第一版建议 30 页，超过时要求管理员改用拆分文件或确认增强解析成本。
- 文件扩展名和 MIME Type 都要校验。
- 拒绝 `.doc`、`.wps`、`.jpg`、`.png` 等非本期范围文件。

响应示例：

```json
{
  "content_type": "standard_script",
  "single_draft": {
    "title": "储能客户价格异议标准话术",
    "category": null,
    "summary": "AI 建议摘要，管理员可修改。",
    "body": "尽量保留原文的完整正文。",
    "structured_payload": {
      "scene": "客户质疑储能系统价格偏高时",
      "recommended_speech": "建议说法原文或近似原文",
      "forbidden_speech": "禁止承诺未审批折扣",
      "notes": "需结合客户峰谷电价和负荷曲线说明收益"
    },
    "warnings": []
  },
  "split_suggestions": [
    {
      "temp_id": "draft-1",
      "suggested_content_type": "standard_script",
      "title": "客户质疑价格偏高时的话术",
      "category": "价格口径",
      "summary": "针对价格异议的标准回复。",
      "body": "该候选草稿对应的原文片段。",
      "structured_payload": {
        "scene": "客户质疑价格偏高",
        "recommended_speech": "候选片段中的推荐说法",
        "forbidden_speech": "候选片段中的禁用说法",
        "notes": "候选片段中的注意事项"
      },
      "source_span": {
        "start_block": 3,
        "end_block": 8
      },
      "confidence": "high",
      "warnings": []
    }
  ],
  "raw_text": "本地解析和 OCR 融合后的原始文本",
  "parse_method": "pdf_hybrid_enhanced",
  "warnings": [
    "第 3 页采用 OCR 结果，建议核对数字和专有名词。",
    "未识别到完整禁用说法，请管理员补充。"
  ],
  "pages": [
    {
      "page": 1,
      "chosen": "local",
      "local_score": 86,
      "ocr_score": 80,
      "warning": null
    },
    {
      "page": 2,
      "chosen": "ocr",
      "local_score": 18,
      "ocr_score": 91,
      "warning": "本页本地文本疑似不完整，已采用 OCR。"
    }
  ]
}
```

注意：该接口只返回解析结果，不创建 `contents` 记录。保存草稿继续复用现有 `POST /api/admin/contents`。

## 6. 后端模块拆分

建议新增以下文件，避免把解析逻辑塞进现有内容服务：

```text
backend/app/api/routes/content_import.py
backend/app/schemas/content_import.py
backend/app/services/document_import_service.py
backend/app/services/document_extractors.py
backend/app/services/document_structuring_service.py
```

职责划分：

- `content_import.py`：FastAPI 路由、权限、文件接收、错误码映射。
- `content_import.py` 或 `schemas/content_import.py`：请求参数和响应结构。
- `document_extractors.py`：DOCX/PDF 本地解析、PDF 渲染、OCR 调用输入准备。
- `document_import_service.py`：编排解析模式、逐页评分、择优融合、输出 `raw_text`。
- `document_structuring_service.py`：调用 `qwen-plus`，把 `raw_text` 转成内容字段 JSON。
- `integrations/dashscope.py`：补充 OCR 和结构化调用所需的客户端方法。

## 7. 依赖建议

后端当前依赖中没有 Word/PDF 解析库。建议新增：

```text
python-docx
PyMuPDF
```

理由：

- `python-docx`：解析 DOCX 段落、标题、列表、表格、内嵌图片关系。
- `PyMuPDF`：PDF 文本提取、页面渲染为图片，避免额外依赖 Poppler。

暂不建议第一版同时引入过多 PDF 库。若后续发现表格还原能力不足，再评估 `pdfplumber`。

## 8. DOCX 解析策略

DOCX 优先本地解析，因为 DOCX 本身有结构化内容。

### 8.1 本地解析内容

- 段落文本：按文档顺序提取。
- 标题样式：记录标题层级，辅助生成标题和段落边界。
- 列表：保留编号和项目符号。
- 表格：按行转换为 Markdown 风格文本，例如 `列1 | 列2 | 列3`。
- 页眉页脚：默认不纳入正文，除非正文为空。
- 空行：合并连续空行。
- 重复内容：去除明显重复的页眉页脚、文件名、页码。

### 8.2 DOCX 图片 OCR

如果 DOCX 中存在图片：

- 提取图片二进制。
- 过滤过小图片，例如 logo、图标。
- 对大图或疑似截图调用 `qwen-vl-ocr-2025-11-20`。
- 图片 OCR 结果插入到图片所在段落附近。
- 返回 warning：`文档包含图片 OCR 内容，请核对识别结果。`

### 8.3 DOCX 输出

DOCX 本地解析结果应包含：

```json
{
  "raw_text": "合并后的原文",
  "blocks": [
    {
      "type": "paragraph",
      "text": "段落文本"
    },
    {
      "type": "table",
      "text": "表格文本"
    },
    {
      "type": "image_ocr",
      "text": "图片 OCR 文本"
    }
  ],
  "warnings": []
}
```

## 9. PDF 解析策略

PDF 不采用单一“本地失败才 OCR”的策略，因为真实 PDF 经常是混合型：部分页面可复制，部分页面是扫描件，部分页面是截图，部分表格页本地解析错乱。

第一版采用两种模式：

### 9.1 快速解析

适合普通文字型 PDF。

流程：

1. 用 PyMuPDF 对每页提取本地文本。
2. 对每页计算本地文本质量分。
3. 抽样 OCR：
   - 第 1 页。
   - 本地文本最少的 1-3 页。
   - 疑似表格页。
   - 本地文本乱码比例高的页。
4. 对抽样页比较本地结果和 OCR 结果。
5. 如果抽样 OCR 明显优于本地解析，返回 warning，建议管理员改用增强解析。
6. 对抽样页可以直接采用更优结果，其余页采用本地结果。

### 9.2 增强解析

适合扫描件、截图多、表格多、格式混乱文档。

流程：

1. 用 PyMuPDF 提取每页本地文本。
2. 用 PyMuPDF 将每页渲染为图片。
3. 每页调用 `qwen-vl-ocr-2025-11-20`。
4. 每页分别计算本地文本质量分和 OCR 文本质量分。
5. 逐页选择更可信的结果。
6. 如果本地和 OCR 差异大，采用分数更高的一路，并追加 warning。
7. 合并全部页面文本。
8. 交给 `qwen-plus` 做结构化整理。

### 9.3 强制 OCR

管理员勾选 `force_ocr=true` 时：

- PDF 每页必须渲染并 OCR。
- 如果本地文本明显好于 OCR，可以在逐页择优时仍选择本地文本，但 warning 要说明“已执行强制 OCR，本页最终采用本地文本，因为文本质量更高”。
- 这样既尊重管理员意图，也避免 OCR 把清晰文本识别错。

## 10. 文本质量评分

评分不追求完美，目标是可解释、可测试、能降低明显错误。

建议每页计算 `0-100` 分：

```text
score =
  有效中英文字符数量得分
  + 标点和段落完整度得分
  + 内容类型关键词命中得分
  - 乱码字符惩罚
  - 单字断行惩罚
  - 重复页眉页脚惩罚
  - 文本过短惩罚
```

有效字符：

- 中文字符。
- 英文和数字。
- 常见业务标点。

乱码指标：

- `�`、控制字符、异常符号比例高。
- 连续不可读字符。
- 中文文档中非中文非英文符号过多。

单字断行指标：

```text
储
能
系
统
```

这类页面本地解析通常不佳，需要 OCR 或后处理。

内容类型关键词：

- 最新必读：`更新`、`调整`、`变更`、`政策`、`注意`、`要求`。
- 核心基础话术：`产品`、`流程`、`客户`、`口径`、`说明`。
- 标准化话术：`场景`、`推荐说法`、`标准话术`、`禁用说法`、`注意事项`。

逐页选择规则：

```text
if local_score >= ocr_score + 8:
    chosen = local
elif ocr_score >= local_score + 8:
    chosen = ocr
else:
    chosen = local if local_text is longer and readable else ocr
```

如果两路分数接近但内容差异大，应追加 warning，提示管理员核对该页。

## 11. 大模型结构化整理

### 11.1 调用模型

使用 `qwen-plus`，通过现有 DashScope OpenAI-compatible chat completions 调用。

输入包括：

- `content_type`
- 文件名
- 解析模式
- 融合后的 `raw_text`
- 逐页 warning
- 目标 JSON schema

输出必须是 JSON，不允许混入解释性文字。

### 11.2 通用约束 Prompt

模型必须遵守：

- 只能基于输入文本整理字段。
- 不得补充输入文本不存在的业务承诺、价格、政策、收益率、期限、风险结论。
- 不默认改写正文和话术。
- 识别不到的字段返回空字符串或空数组。
- 对不确定内容写入 `warnings`。
- `body` 应尽量保留原文主要内容。
- `summary` 可以压缩整理，但不能改变原意。

### 11.3 三类内容字段映射

核心基础话术 `base_script`：

```json
{
  "title": "",
  "summary": "",
  "body": "",
  "structured_payload": {
    "points": []
  },
  "warnings": []
}
```

标准化话术 `standard_script`：

```json
{
  "title": "",
  "summary": "",
  "body": "",
  "structured_payload": {
    "scene": "",
    "recommended_speech": "",
    "forbidden_speech": "",
    "notes": ""
  },
  "warnings": []
}
```

最新必读 `must_read`：

```json
{
  "title": "",
  "summary": "",
  "body": "",
  "structured_payload": {
    "update_body": "",
    "adjustment_points": []
  },
  "warnings": []
}
```

### 11.4 结果校验

后端不能直接信任模型输出，必须做校验：

- JSON 必须可解析。
- 必填字段缺失时补默认值。
- 字段类型错误时转换或置空。
- `title` 为空时使用文件名。
- `body` 为空时使用 `raw_text`。
- `summary` 过长时截断到合理长度，建议 500 字以内。
- `adjustment_points` 必须是字符串数组。
- `structured_payload` 必须符合所选内容类型。
- 对模型输出中疑似新增的业务承诺无法完全自动判断，因此必须保留管理员人工确认流程。

## 12. 单条草稿、拆解候选与无结构文档处理

### 12.1 双出口原则

每次上传解析后，系统都应该同时提供两个出口：

```text
single_draft：单条草稿建议，永远生成，默认使用
split_suggestions：拆解候选草稿列表，可为空，只作为建议
```

这样可以避免系统在“拆不拆”上做不可逆决定：

- 文档很短或边界不清晰时，管理员可以直接使用单条草稿。
- 文档很长、包含多个主题时，管理员可以查看拆解候选。
- 拆解候选不自动保存，不自动发布，必须管理员勾选确认。

### 12.2 何时建议拆解

系统可以提示“建议拆解”，但不强制拆解。触发提示的条件包括：

- 文档超过 5000 字。
- PDF 超过 10 页。
- 检测到多个一级/二级标题。
- 检测到多个编号段落，例如 `一、`、`1.`、`1.1`。
- 检测到多个 `场景`、`推荐说法`、`禁用说法`、`注意事项` 组合。
- 检测到多个独立表格块。
- `qwen-plus` 判断包含多个独立主题，并给出中高置信度。

提示文案示例：

```text
检测到该文档可能包含多个独立内容片段，已生成拆解建议。你也可以继续使用单条草稿。
```

### 12.3 拆解边界规则

拆解不能完全交给模型自由发挥，应采用“结构分段 + 保守合并 + 模型判断 + 后端硬校验”。

第一层：结构分段。

- DOCX 标题层级。
- PDF 页码。
- 编号标题，如 `一、`、`1.`、`1.1`。
- 表格块。
- 明显分隔线。
- 业务标题，如 `场景`、`推荐说法`、`禁用说法`、`更新内容`、`调整要点`。

第二层：保守合并。

- 少于 300 字的片段默认和前后相邻片段合并。
- 只有标题没有正文的片段必须合并。
- 同一标题下的多个小段必须合并。
- 同一标准化话术的 `场景 + 推荐说法 + 禁用说法 + 注意事项` 必须合成一条候选草稿。
- 相邻片段如果同属一个产品、一个政策、一个客户场景，优先合并。
- 边界不清晰时，宁可合并，不要拆碎。

第三层：模型建议。

`qwen-plus` 可以判断：

- 某个片段是否像独立内容。
- 应该归入哪种内容类型。
- 是否应该和上一段或下一段合并。
- 标题、摘要、字段建议。
- 拆解置信度和风险提示。

第四层：后端硬校验。

- 拆解候选最多 20 条。
- 每条候选必须引用原始片段范围，例如 `source_span.start_block/end_block`。
- 每条候选必须保留原文片段，不能只返回改写结果。
- 低置信度候选不默认勾选。
- 过短候选不允许直接通过，除非是结构完整的标准化话术短条目。
- 模型不得返回原文不存在的业务承诺、价格、期限、收益率、政策边界。

### 12.4 无结构或结构不清晰文档

如果上传文档没有清晰标题、编号、表格边界，系统不应强行拆碎。

处理策略：

```text
无结构全文
  -> 按段落和长度形成粗窗口
  -> 用语义相似度和主题变化点判断可能边界
  -> 只生成高置信拆解候选
  -> 边界不清晰时少拆或不拆
  -> 单条草稿始终可用
```

保守规则：

- 低于 1500-2000 字的短文档默认不建议拆，除非有非常强的业务结构信号。
- 语义间隙大但每段都很短时，不直接拆成很多小候选，应先合并成更完整主题块。
- 只有当一个候选能独立回答“它讲什么、适用什么场景、有哪些口径或要求”时，才建议成为草稿。
- 对低置信边界追加 warning，例如 `该候选与前后片段主题接近，建议管理员确认是否合并。`

### 12.5 拆解结果前端操作

拆解候选 Tab 中建议支持：

- 勾选/取消候选。
- 修改标题、分类、内容类型、权限级别、可见范围。
- 展开查看候选正文。
- 删除候选。
- 合并相邻候选。
- 第一版暂不支持任意手动画线拆分。

保存时：

- “使用单条草稿”只填入当前表单或保存一条草稿。
- “保存选中为草稿”批量调用现有创建内容接口。
- 未勾选候选不保存。
- 全部保存结果仍为 `draft`，不自动发布。

## 13. 发布后的检索切分与 MySQL/Milvus 对齐

### 13.1 当前已经实现的切分策略

当前发布后的检索分块在 `backend/app/services/rag_index_service.py` 的 `build_chunk_specs` 中生成：

- `base_script`：通常生成 1 个 `base_script_body` chunk，包含标题、分类、摘要、正文、要点。
- `must_read`：通常生成 1 个 `must_read_update` chunk，包含标题、分类、摘要、更新正文、调整要点。
- `standard_script`：通常生成 1 个 `standard_script_scene` chunk。
- 如果 `standard_script.structured_payload.items` 是数组，则每个 item 生成 1 个 `standard_script_scene` chunk。

当前系统没有通用的“按长度滑窗切分”策略。因此多数内容看起来是一条发布内容对应一条 `content_chunks`，但表结构已经支持一条内容对应多个 chunk。

### 13.2 三层数据关系

必须区分三层：

```text
contents / content_versions：业务内容和完整发布版本
content_chunks：MySQL 中的权威检索分块
Milvus vector：content_chunks 的向量索引
```

关系原则：

- `content_versions` 保存完整发布内容。
- `content_chunks` 保存用于检索的若干片段。
- 一个 `content_chunk` 对应一个 Milvus vector。
- Milvus metadata 必须带 `content_id`、`version_id`、`chunk_id`。
- Milvus 不允许脱离 MySQL 私自切分。
- 检索命中后必须回查 MySQL `content_chunks`，再校验发布状态、当前版本、权限级别、部门范围。

当前 `sync_content_index` 已经按这个方向实现：

```text
active_current_chunks
  -> 对每个 content_chunk 调用 embed_text
  -> Milvus primary_key = content-{content.id}-version-{chunk.version_id}-chunk-{chunk.id}
  -> Milvus metadata 写入 content_id/version_id/chunk_id/权限/部门/状态
  -> MySQL vector_index_records 记录 chunk 和 Milvus 主键
```

检索时：

```text
Milvus 命中 chunk_id
  -> db.get(ContentChunk, chunk_id)
  -> 校验 content.status = published
  -> 校验 content.current_version_id = chunk.version_id
  -> 校验 content.permission_level 和 chunk.permission_level
  -> 校验 content.scope_type/department_id 和 chunk.scope_type/department_id
  -> 使用 MySQL chunk_text 作为回答上下文
```

因此，真正的答案来源始终是 MySQL，不是 Milvus。

### 13.3 导入拆解与检索切分的关系

导入阶段的拆解候选是业务草稿拆分，不等于最终检索 chunk。

示例：

```text
上传大文档
  -> single_draft
  -> split_suggestions: 候选 A、候选 B、候选 C
  -> 管理员选择候选 A 保存为 contents A 草稿
  -> 管理员发布 contents A
  -> 生成 content_versions A-v1
  -> 发布阶段生成 content_chunks A-1、A-2、A-3
  -> Milvus 分别索引 A-1、A-2、A-3
```

也就是说：

- 拆解候选负责“业务完整性”和“管理员维护粒度”。
- 检索切分负责“召回质量”和“上下文长度控制”。
- 即使一个候选草稿已经是大文档拆出来的，发布后仍然应该再按检索策略生成 `content_chunks`。

### 13.4 后续检索切分增强建议

发布阶段应增强 `build_chunk_specs`，把过长内容切成多个 MySQL `content_chunks`，而不是让 Milvus 独立切。

推荐策略：

- 先按业务结构切分：
  - 标准化话术按场景 item。
  - 最新必读按更新点、调整要点或小标题。
  - 核心基础话术按标题、小节、段落。
- 如果单个业务块仍然过长，再按段落和长度切成 retrieval chunks。
- 每个 retrieval chunk 写入 MySQL `content_chunks`。
- 每个 retrieval chunk 分别写入 Milvus。
- 每个 chunk 都注入标题、分类、摘要、内容类型、当前小节标题作为前缀。

建议参数：

```text
chunk_size: 800-1200 中文字
overlap: 150-250 中文字
```

示例：

```text
content_versions.body = 完整发布正文

content_chunks:
1. 标题 + 摘要 + 第 1-3 段
2. 标题 + 摘要 + 第 3-5 段
3. 标题 + 摘要 + 第 5-7 段

Milvus:
vector 1 -> chunk_id 1
vector 2 -> chunk_id 2
vector 3 -> chunk_id 3
```

### 13.5 召回不断裂策略

如果只按拆解候选硬切，边界切错时可能导致召回丢上下文。因此必须用检索切分兜住语义连续性。

推荐三件事：

1. 每个 chunk 注入标题、摘要、分类、小节标题，保证片段知道自己属于哪个主题。
2. 相邻 chunk 使用 overlap，避免答案刚好跨在边界上。
3. 命中某个 chunk 后，可在 MySQL 层补相邻 chunk。

补相邻 chunk 不需要 Milvus 再查一次，因为 MySQL `content_chunks` 有：

```text
content_id
version_id
sort_order
```

命中 `sort_order = 3` 时，可以回查：

```text
same content_id
same version_id
sort_order in [2, 3, 4]
is_active = true
```

然后把相邻 chunk 拼入同一个上下文。当前 `load_authorized_contexts` 已经会把同一个 content 命中的多个 chunk 合并；后续可以增强为“命中 chunk 后主动补前后相邻 chunk”。

### 13.6 最终对齐原则

最终必须满足：

- 保存草稿只写 `contents` 草稿，不写 `content_chunks`，不写 Milvus。
- 发布内容时写 `content_versions` 和 `content_chunks`。
- `content_chunks` 是 MySQL 权威检索片段。
- Milvus 一条 vector 对应一条 `content_chunks`。
- Milvus metadata 永远包含 `chunk_id`。
- 检索结果永远回查 MySQL chunk。
- 上下文扩展通过 `content_id/version_id/sort_order` 查相邻 MySQL chunk。
- 不存在“Milvus 私自切了一个 MySQL 找不到的子块”的情况。

## 14. 数据库与表结构决策

### 14.1 第一版不扩表、不新增表

第一版不建议扩展原表字段，也不建议新增导入业务表。现有表已经足够支撑“上传解析、管理员确认、保存草稿、发布后索引”这条链路。

原因：

- 上传解析结果在保存前只是临时建议，不需要落库。
- `single_draft` 和 `split_suggestions` 可以直接返回给前端展示。
- 管理员确认后，单条草稿或被选中的拆解候选都可以复用现有 `POST /api/admin/contents` 保存。
- 保存后的内容已经进入 `contents`，后续由现有发布链路接管。
- 不保存上传原文件。
- 不保存导入任务历史。
- 不需要异步队列。
- 不需要管理员回看历史解析结果。
- 不需要候选草稿跨天暂存。

因此第一版可以做到：

```text
不扩展 contents
不扩展 content_versions
不扩展 content_chunks
不新增 content_import_jobs
不新增 content_import_candidates
不新增数据库迁移
```

### 14.2 现有表如何承载

`contents` 保存草稿主体：

```text
title
content_type
category
permission_level
scope_type
department_id
draft_summary
draft_body
draft_payload
status = draft
```

`content_versions` 保存发布后的完整版本：

```text
title
summary
body
structured_payload
permission_level
scope_type
department_id
```

`content_chunks` 保存发布后的 MySQL 权威检索分块：

```text
content_id
version_id
chunk_type
chunk_text
sort_order
content_hash
permission_level
scope_type
department_id
is_active
```

`vector_index_records` 保存 MySQL chunk 和 Milvus vector 的对应关系：

```text
chunk_id
milvus_primary_key
embedding_model
embedding_dimension
is_active
```

这已经覆盖：

- 单条草稿保存。
- 拆解候选保存成多条草稿。
- 发布版本。
- 发布后检索分块。
- Milvus 向量与 MySQL chunk 对齐。

### 14.3 什么时候才需要新增表

只有当后续要做以下能力时，才考虑新增导入相关表：

1. 导入任务历史：管理员能回看某次上传、解析结果、失败原因。
2. 异步解析：大 PDF OCR 很慢，需要 `pending/processing/completed/failed` 状态。
3. 保存原文件：需要追溯源文件、重新解析、下载附件。
4. 解析结果审计：需要记录 AI 输出、OCR 文本、管理员修改前后差异。
5. 批量导入草稿暂存：管理员今天不想保存，明天继续处理候选列表。

届时可以新增：

```text
content_import_jobs
content_import_candidates
```

但这不是第一版必须项。

### 14.4 content_chunks 是否需要扩字段

第一版也不强制扩展 `content_chunks`。现有字段已经可以通过：

```text
content_id + version_id + sort_order
```

定位同一内容同一版本下的前后相邻 chunk，从而支持召回后补相邻上下文。

如果后续要做更精确的来源定位，可以再考虑给 `content_chunks` 增加：

```text
parent_chunk_id
source_start_offset
source_end_offset
section_title
```

但第一版不是必需。先用现有 `chunk_type/chunk_text/sort_order` 把长内容切分、索引、召回跑通即可。

## 15. 前端交互设计

在后台“新建内容”页增加“从 Word/PDF 导入”区域。

建议放在内容类型选择之后，正文表单之前：

```text
从 Word/PDF 导入
[选择文件] 支持 .docx / .pdf，建议不超过 20MB
解析模式：[快速解析] [增强解析]
[ ] 强制 OCR
[解析并填入表单]
```

交互规则：

- 未选择内容类型时，禁用上传解析按钮。
- 编辑已有内容时第一版不展示导入区，避免覆盖已有草稿。
- 上传解析期间显示 loading。
- 解析成功后展示两个 Tab：`单条草稿` 和 `拆解候选`。
- 默认选中 `单条草稿`，并提供“填入当前表单”按钮。
- `拆解候选` 可为空；为空时展示“未识别到可靠拆解边界，可使用单条草稿”。
- 拆解候选列表支持勾选、取消、编辑基础字段、删除、合并相邻候选。
- `保存选中为草稿` 只保存管理员勾选的候选。
- 如果表单已有内容，点击解析前二次确认：`解析结果会覆盖当前表单内容，是否继续？`
- 展示 `warnings`，例如：
  - `第 3 页采用 OCR 结果，建议核对数字和专有名词。`
  - `未识别到禁用说法，请管理员补充。`
  - `该文档边界不清晰，拆解候选仅供参考。`
- 展示 `parse_method` 的人类可读说明：
  - `DOCX 本地解析`
  - `DOCX 本地解析 + 图片 OCR`
  - `PDF 快速解析`
  - `PDF 增强解析`
- 上传 `.doc` 时不调用后端解析，前端直接提示：`仅支持 .docx 和 .pdf。老版 .doc 文件请另存为 .docx 后上传。`
- 不在员工端展示任何导入状态。

## 16. 错误处理

后端建议统一错误码：

| 错误码 | HTTP | 场景 | 前端提示 |
| --- | --- | --- | --- |
| `unsupported_file_type` | 422 | 非 docx/pdf | 仅支持 Word docx 和 PDF 文件 |
| `file_too_large` | 413 | 文件超过限制 | 文件过大，请拆分后上传 |
| `pdf_too_many_pages` | 422 | PDF 页数超过限制 | PDF 页数过多，请拆分后上传 |
| `empty_document` | 422 | 本地和 OCR 都无有效文本 | 未识别到有效文本，请检查文件 |
| `ocr_page_limit_exceeded` | 422 | OCR 页数超过限制 | OCR 页数过多，请拆分文件或选择快速解析 |
| `provider_timeout` | 503 | DashScope 超时 | 模型服务超时，请稍后重试 |
| `provider_authentication_failed` | 503 | API Key 错误 | 模型服务认证失败，请检查配置 |
| `provider_response_invalid` | 503 | 模型返回不可解析 | 模型返回异常，请重试 |

所有错误都不得泄露 API Key、内部栈信息、服务器路径。

## 17. 配置项

建议在 `Settings` 增加：

```text
dashscope_ocr_model=qwen-vl-ocr-2025-11-20
dashscope_vision_model=qwen3.5-flash
content_import_max_file_mb=20
content_import_max_pdf_pages=80
content_import_max_ocr_pages=30
content_import_default_parse_mode=fast
```

现有配置继续复用：

```text
dashscope_base_url=https://dashscope.aliyuncs.com/compatible-mode/v1
dashscope_chat_model=qwen-plus
dashscope_embedding_model=text-embedding-v4
dashscope_http_timeout_seconds=8.0
```

不要把 DashScope API Key 写入代码、测试文件、文档或 Git。

## 18. 与现有内容发布链路的关系

导入解析只发生在草稿创建前，不改变现有核心模型：

```text
导入解析结果
  -> single_draft 或管理员选中的 split_suggestions
  -> 前端表单或批量保存草稿
  -> POST /api/admin/contents 保存 contents 草稿
  -> 管理员发布
  -> content_versions 生成版本
  -> replace_chunks_for_version 生成 MySQL content_chunks
  -> sync_content_index 按 content_chunks 写入 Milvus
  -> 员工端和 AI 检索可见
```

因此：

- 权限级别、部门范围仍由管理员在表单中选择。
- 内容状态仍是 `draft`。
- 草稿不进入员工端列表。
- 草稿不进入 AI 检索。
- 发布后才会生成版本和索引。
- 发布后 `content_versions` 保存完整正文，`content_chunks` 保存检索分块。
- Milvus 只索引 MySQL `content_chunks`，不独立私自切分。

## 19. 测试方案

### 19.1 后端单元测试

新增测试文件建议：

```text
backend/tests/test_content_import_phase12.py
```

测试点：

1. 非管理员调用 `/api/admin/content-import/parse` 返回 403。
2. 未登录调用返回 401。
3. 上传 `.txt` 返回 `unsupported_file_type`。
4. 上传 `.doc` 返回 `unsupported_file_type`，提示另存为 `.docx`。
5. 上传超大文件返回 `file_too_large`。
6. `content_type` 非法返回 422。
7. DOCX 段落解析能保留段落顺序。
8. DOCX 表格解析能转成可读文本。
9. DOCX 内嵌图片时会调用 fake OCR，并把 OCR 文本插入 `raw_text`。
10. PDF 本地文本解析能按页返回文本。
11. PDF 快速解析会抽样 OCR 指定页。
12. PDF 增强解析会对每页执行 OCR。
13. `force_ocr=true` 时会执行 OCR。
14. 逐页评分中，乱码本地文本应输给 OCR 文本。
15. 逐页评分中，清晰本地文本应优先于较差 OCR 文本。
16. 模型结构化返回非法 JSON 时返回 `provider_response_invalid`。
17. 模型结构化缺字段时，后端会补默认值。
18. 每次解析响应都必须包含 `single_draft`。
19. `split_suggestions` 可以为空，但必须是数组。
20. 无结构短文档默认不生成过碎拆解候选。
21. 少于 300 字的短片段会被合并到相邻片段。
22. 拆解候选最多 20 条。
23. 拆解候选必须包含 `source_span` 和 `confidence`。
24. `standard_script` 结果必须包含 `scene/recommended_speech/forbidden_speech/notes`。
25. `must_read` 结果必须包含 `update_body/adjustment_points`。
26. `base_script` 结果必须包含 `points`。
27. 解析接口不会创建 `contents` 数据库记录。
28. 保存拆解候选为草稿时，只创建管理员选中的候选。
29. 保存草稿不会创建 `content_chunks` 或 Milvus 向量记录。

### 19.2 DashScope 客户端测试

扩展现有 `backend/tests/test_dashscope_http_phase11.py`：

1. OCR 请求使用 `dashscope_ocr_model`。
2. OCR 图片以 data URL 或官方支持的图片输入格式传入。
3. OCR 返回文本能被标准化成内部结果。
4. OCR 超时会标准化为 `provider_timeout`。
5. OCR 401/403 会标准化为 `provider_authentication_failed`。
6. 结构化整理请求使用 `qwen-plus`。
7. 结构化整理要求 JSON 输出。
8. 模型返回空内容时报 `provider_response_invalid`。

### 19.3 前端单元测试

新增或扩展：

```text
frontend/tests/admin-content-import.test.ts
```

测试点：

1. 新建内容页展示 Word/PDF 导入区。
2. 编辑已有内容页不展示导入区。
3. 未选择内容类型时，解析按钮禁用。
4. 选择文件和内容类型后，点击解析会调用 `/admin/content-import/parse`。
5. 上传 `.doc` 时前端提示另存为 `.docx`，不调用后端。
6. 解析成功后展示 `单条草稿` 和 `拆解候选` Tab。
7. 单条草稿能填入标题、摘要、正文。
8. `standard_script` 会填入场景、推荐说法、禁用说法、注意事项。
9. `must_read` 会填入更新正文、调整要点。
10. 拆解候选为空时显示“未识别到可靠拆解边界”提示。
11. 拆解候选可以勾选、取消、删除、合并相邻候选。
12. 保存选中候选时只提交被勾选的候选。
13. 返回 `warnings` 时页面展示警告。
14. 表单已有内容时，点击解析前会二次确认覆盖。
15. 解析失败时显示明确错误，不清空已有表单。
16. 快速/增强解析模式会作为参数传给后端。
17. 强制 OCR 勾选状态会作为参数传给后端。

### 19.4 集成测试

后端集成测试可使用小型测试文件：

```text
backend/tests/fixtures/import/base_script_sample.docx
backend/tests/fixtures/import/standard_script_sample.docx
backend/tests/fixtures/import/must_read_sample.pdf
```

如果不希望把二进制样例放入 Git，可以在测试中动态生成 DOCX 和 PDF。动态生成更干净，但测试代码稍复杂。

集成测试目标：

1. DOCX 样例上传后返回可用草稿字段。
2. PDF 样例上传后返回可用草稿字段。
3. 返回结果必须包含 `single_draft`。
4. 大文档样例返回 `split_suggestions`，且候选数量不超过 20。
5. 无结构短文档样例不应被拆成过多候选。
6. 返回的 `single_draft` 可以直接作为 `POST /api/admin/contents` 的 payload 保存草稿。
7. 管理员选中的 `split_suggestions` 可以批量保存为多条草稿。
8. 保存草稿后状态为 `draft`。
9. 草稿不会出现在员工端 `/api/app/must-reads` 或 `/api/app/scripts`。
10. 发布草稿后生成 `content_versions` 和 `content_chunks`。
11. 同步索引后，Milvus fake client 中每条 vector 的 metadata 都能回查到 MySQL `content_chunks.id`。
12. 下线或重新发布新版本后，旧 `content_chunks` 和旧向量记录不再作为 active 结果使用。

### 19.5 手工验收测试

准备 8 类真实文件：

1. 纯文字 DOCX。
2. 带表格 DOCX。
3. 带截图 DOCX。
4. 可复制文字 PDF。
5. 扫描版 PDF。
6. 混合 PDF：部分文本、部分扫描。
7. 表格密集 PDF。
8. 格式很乱的业务文档。

每类文件按三种内容类型分别试一次，重点验收：

- 能否解析出有效 `raw_text`。
- 是否填入正确表单字段。
- 是否始终有单条草稿。
- 大文档是否给出合理拆解候选。
- 无结构短文档是否没有被过度拆碎。
- 是否展示必要 warning。
- 数字、价格、日期、政策边界是否需要人工核对提示。
- 点击保存后只生成草稿。
- 未发布前员工端不可见。
- 发布后员工端和 AI 检索按原有权限规则可见。
- AI 检索命中来源能定位到发布内容，并能通过 `chunk_id` 回查到 MySQL `content_chunks`。

### 19.6 回归测试

实现完成后必须跑：

```powershell
cd E:\WeView\work4\backend
..\.venv\Scripts\python.exe -m pytest tests -q

cd E:\WeView\work4\frontend
corepack.cmd pnpm test:unit
corepack.cmd pnpm build
```

如改动了前端交互，需用内置浏览器验证：

1. 管理员登录。
2. 进入“内容管理”。
3. 点击“新建内容”。
4. 选择内容类型。
5. 上传 DOCX/PDF。
6. 点击“解析并填入表单”。
7. 检查字段和 warning。
8. 保存草稿。
9. 回到列表确认草稿存在。
10. 不发布时，员工端不可见。

## 20. Bug 风险与防护

### 20.1 模型幻觉

风险：大模型补充原文不存在的业务结论。

防护：

- Prompt 明确禁止补充。
- 正文和话术尽量保留原文。
- 所有结果必须管理员人工确认。
- 对模型整理结果展示 warning。

### 20.2 OCR 错数字

风险：金额、日期、比例、收益率、型号被识别错。

防护：

- OCR 页追加 warning。
- 对包含数字密集内容的页追加“请核对数字”提示。
- 管理员发布前必须人工检查。

### 20.3 PDF 页丢失

风险：本地解析只拿到部分页。

防护：

- 统计 PDF 总页数。
- 响应中返回每页解析状态。
- 增强模式逐页 OCR。

### 20.4 表格错乱

风险：表格列错位导致话术含义变化。

防护：

- DOCX 表格用行列结构转文本。
- PDF 表格页在快速模式中加入 OCR 抽样。
- 表格页 warning 提示管理员核对。

### 20.5 覆盖表单

风险：管理员已经手工输入内容后上传解析，覆盖已有内容。

防护：

- 前端检测表单已有内容。
- 解析前二次确认。
- 解析失败不清空表单。

### 20.6 成本和超时

风险：增强解析每页 OCR，成本和耗时较高。

防护：

- 解析模式明确提示。
- 设置 OCR 页数上限。
- 超时返回可理解错误。
- 默认快速解析，管理员可主动选增强解析。

### 20.7 拆解过碎

风险：短文档或无结构文档因为语义间隙大，被模型拆成很多过碎候选，导致管理员难以使用，后续检索上下文也变差。

防护：

- 单条草稿始终可用，并默认展示。
- 拆解候选只作为建议，不自动保存。
- 低于 1500-2000 字的短文档默认不建议拆。
- 少于 300 字的短片段默认合并。
- 边界不清晰时宁可合并，不拆碎。
- 低置信候选不默认勾选。
- 候选总数限制为 20 条。

### 20.8 拆解边界导致召回断裂

风险：业务拆解候选边界切错，后续检索只命中某一半上下文。

防护：

- 业务拆解不等于检索切分。
- 发布阶段对每条内容重新生成检索 `content_chunks`。
- 过长 chunk 按段落和长度二次切分，并使用 overlap。
- 每个 chunk 注入标题、摘要、分类、小节标题。
- 命中 chunk 后可在 MySQL 层补前后相邻 chunk。

### 20.9 MySQL 与 Milvus 不对齐

风险：Milvus 私自切分出 MySQL 中不存在的子块，检索命中后无法可靠回查来源、权限和版本。

防护：

- Milvus 不独立私切。
- 所有检索子块必须先写入 MySQL `content_chunks`。
- 一个 `content_chunk` 对应一个 Milvus vector。
- Milvus metadata 必须包含 `chunk_id`。
- 回答前永远用 `chunk_id` 回查 MySQL，并重新做权限、版本、状态校验。

## 21. 推荐实施顺序

1. 增加配置和 DashScope OCR/结构化客户端方法。
2. 实现 DOCX 本地解析。
3. 实现 PDF 本地文本提取和页面渲染。
4. 实现 OCR 调用和 fake OCR 测试客户端。
5. 实现逐页质量评分和快速/增强模式。
6. 实现 `qwen-plus` 单条草稿结构化整理。
7. 实现拆解候选生成、保守合并、候选数量限制和低置信 warning。
8. 新增 `/api/admin/content-import/parse`。
9. 前端新建内容页增加导入区、单条草稿 Tab 和拆解候选 Tab。
10. 增强发布阶段 `build_chunk_specs`：长内容生成多个 MySQL `content_chunks`，Milvus 跟随 chunk 索引。
11. 增强召回：命中 chunk 后可补相邻 chunk。
12. 补齐后端、前端、集成测试。
13. 内置浏览器做管理员导入草稿验收。

## 22. 最终验收标准

功能可以认为达标，必须同时满足：

- 管理员能上传 DOCX/PDF 并得到草稿建议。
- `.doc` 文件会被明确拒绝，并提示另存为 `.docx`。
- 三类内容都能填入各自对应字段。
- 每次解析都生成单条草稿。
- 大文档可以生成可控拆解候选。
- 无结构短文档不会被过度拆碎。
- PDF 混合文档在增强模式下不会整页丢失。
- OCR 页和低置信字段有 warning。
- 解析不会自动发布。
- 解析不会创建向量索引。
- 保存草稿不会创建 `content_chunks` 或 Milvus 向量。
- 发布后生成 MySQL `content_chunks`。
- Milvus vector 与 MySQL `content_chunks` 一一对应。
- 检索命中后能通过 `chunk_id` 回查 MySQL，并完成权限、版本、部门范围校验。
- 非管理员不能调用解析接口。
- 解析失败不会破坏已有表单内容。
- 后端测试、前端测试、前端构建全部通过。
- 浏览器手工验收通过。
