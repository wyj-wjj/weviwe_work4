# 测验题与内容更新联动机制设计说明

## 1. 文档目的

本文用于固定“测验题模块后续演进”的产品与技术边界，避免后续实现时发生概念漂移。

本设计覆盖以下问题：

- 测验题是否作为独立模块存在。
- 测验题如何绑定最新必读、标准话术和内容版本。
- 内容发布时如何区分小更新、中更新、大更新。
- AI 出题与管理员人工审核的边界。
- 数据库表字段应如何扩展。
- 大更新专题测验、旧题复核、题目失效如何处理。

本文暂不设计员工答题记录、考试得分、完成率统计、排名、强制考核等能力。

## 2. 核心结论

测验题应采用：

```text
独立题库管理
  + 内容/版本绑定
  + 内容发布时标记更新级别
  + AI 生成候选题
  + 管理员审核启用
  + 大更新触发专题测验包
```

也就是说：

- 员工端继续保留独立“巩固测试”入口。
- 后台继续保留独立“测验题管理”入口。
- 题目不直接写死在内容正文里。
- 题目可以绑定某条内容，也应支持绑定某个发布版本。
- AI 可以辅助生成题目草稿，但不能直接自动启用题目。
- 内容更新级别是发布版本的一项属性，不替代版本号。

## 3. 概念边界

### 3.1 内容版本与更新级别

`version_no` 和 `update_level` 是两个不同维度，必须并存。

```text
version_no = 第几次发布，例如 v1、v2、v3
update_level = 本次发布影响有多大，例如 minor、medium、major
```

示例：

| 发布版本 | 更新级别 | 含义 |
| --- | --- | --- |
| v1 | major | 首次正式发布，通常视为完整知识上线 |
| v2 | minor | 改错别字、优化表达，不影响题目 |
| v3 | medium | 局部规则或话术变化，需要复核关联题 |
| v4 | major | 关键规则变化，需要生成专题测验 |

结论：

- `content_versions.version_no` 解决“这是第几版”。
- `content_versions.update_level` 解决“这一版变化大不大”。
- `content_versions.quiz_action` 解决“这一版要如何处理测验题”。

### 3.2 独立题库与内容绑定

测验题仍然是独立资源，不从属于某篇文章页面。

但每道题应可以绑定来源：

```text
related_content_id   = 题目关联哪条内容
related_version_id   = 题目基于哪一个发布版本产生或审核
```

这样可以回答：

- 这道题来自哪篇最新必读或哪条标准话术？
- 这道题基于 v1、v2 还是 v3？
- 内容更新后，这道题是否可能过期？
- 旧版本内容下线或变化后，哪些题目需要复核？

### 3.3 AI 出题与人工审核

AI 只能生成候选题，不能直接生成已启用题。

标准流程：

```text
内容发布
  -> 系统读取当前发布版本
  -> AI 生成候选题
  -> 候选题进入待审核状态
  -> 管理员检查题干、选项、答案、解析、权限、来源
  -> 管理员确认后启用
  -> 员工端巩固测试可抽取
```

原因：

- 测验题有标准答案，答案错误会直接误导员工。
- AI 可能生成超出原文的信息。
- AI 可能把旧规则与新规则混淆。
- 管理员必须对最终题目质量负责。

## 4. 小更新、中更新、大更新边界

更新级别不按修改字数判断，而按业务影响判断。

核心判断句：

```text
这次更新会不会改变员工对客户说什么、承诺什么、判断什么、操作什么？
```

如果不会，通常是小更新。
如果会，则至少是中更新。
如果员工不知道会明显误导客户、踩红线或造成业务风险，则是大更新。

### 4.1 小更新：minor

定义：

不改变业务规则、答案、流程、风险边界，只是文字、格式或表达优化。

典型场景：

- 修改错别字、标点、排版。
- 优化措辞，但含义不变。
- 调整标题、摘要、分类。
- 补充背景说明，但不改变判断结论。
- 增加示例，但原规则没有变化。

题库处理：

- 不强制生成新题。
- 不标记旧题待复核。
- 原启用题继续有效。
- 可记录 `quiz_action = none`。

### 4.2 中更新：medium

定义：

局部知识点、参数、流程或话术表达发生变化。员工需要知道，但影响范围有限。

典型场景：

- 某个参数范围调整。
- 某个流程新增一个注意事项。
- 推荐话术发生变化，但业务规则没有根本变化。
- 禁用话术新增一句。
- 某类客户场景的回答方式变化。
- 最新必读补充一个新要求，但不是系统性变化。

题库处理：

- 与该内容关联的旧题标记为待复核。
- AI 可建议生成 1 到 3 道候选题。
- 管理员复核旧题后，可以继续启用、编辑后启用或禁用。
- 可记录 `quiz_action = review_related`。

### 4.3 大更新：major

定义：

关键业务规则、合规要求、风险边界或客户承诺口径发生明显变化。员工不知道这次更新会明显答错、误导客户或造成风险。

典型场景：

- 消防验收要求变化。
- 并网验收标准变化。
- 补贴政策变化。
- 合同关键条款变化。
- 投资收益测算口径变化。
- 电价政策变化。
- 安全红线变化。
- 原来能承诺的，现在不能承诺。
- 原来不能说的，现在必须提醒。
- 旧题答案可能直接变错。

题库处理：

- 自动创建或建议创建“大更新专题测验包”。
- AI 生成 5 到 10 道候选题。
- 与该内容相关的旧题批量标记为待复核。
- 明显过期的旧题建议禁用。
- 员工端巩固测试优先抽取该专题题。
- 可记录 `quiz_action = generate_pack`。

## 5. 发布流程

### 5.1 管理员发布内容

管理员点击发布时，系统应要求确认本次更新级别。

推荐交互：

```text
本次更新级别：

1. 小更新
   文字、格式、补充说明，不影响测验题

2. 中更新
   局部规则或话术变化，需要复核关联题

3. 大更新
   关键业务规则变化，需要生成专题测验
```

### 5.2 AI 辅助判断

AI 可以根据新旧版本差异给出建议，但最终由管理员确认。

示例：

```text
AI 建议：大更新
原因：本次内容涉及“消防验收要求”和“客户承诺边界”，旧题答案可能过期。
建议动作：生成专题测验候选题，并复核关联旧题。
```

注意：

- AI 建议不自动写死为最终更新级别。
- 管理员可以覆盖 AI 建议。
- 系统应记录管理员最终选择。

### 5.3 发布后的题库动作

```text
minor:
  不生成题
  不复核旧题

medium:
  标记关联旧题 needs_review = true
  可生成少量候选题

major:
  标记关联旧题 needs_review = true
  生成候选题
  建议创建专题测验包
```

## 6. 数据库扩展建议

### 6.1 `content_versions` 扩展

更新级别属于某一次发布版本，因此应放在 `content_versions`，不是放在 `contents`。

建议新增字段：

```text
update_level
change_summary
quiz_action
ai_suggested_update_level
ai_suggestion_reason
```

字段说明：

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| `update_level` | string enum | 管理员确认后的更新级别：`minor`、`medium`、`major` |
| `change_summary` | text nullable | 管理员填写或 AI 辅助生成的本次变更摘要 |
| `quiz_action` | string enum | 本次发布对题库的动作：`none`、`review_related`、`generate_pack` |
| `ai_suggested_update_level` | string nullable | AI 建议的更新级别，仅供参考 |
| `ai_suggestion_reason` | text nullable | AI 判断理由 |

约束：

- `version_no` 继续保留，用于表示 v1、v2、v3。
- `update_level` 不替代 `version_no`。
- 首次发布 v1 默认建议为 `major`，但管理员可确认。

### 6.2 `quiz_questions` 扩展

当前题目表已有 `related_content_id`，后续需要支持版本绑定、生成来源、审核状态和复核状态。

建议新增字段：

```text
related_version_id
source_type
review_status
generation_batch_id
needs_review
review_reason
expires_at
priority
```

字段说明：

| 字段 | 类型建议 | 含义 |
| --- | --- | --- |
| `related_version_id` | int nullable FK | 题目基于哪个 `content_versions.id` 生成或审核 |
| `source_type` | string enum | 题目来源：`manual`、`ai_generated`、`ai_assisted` |
| `review_status` | string enum | 审核状态：`draft`、`pending_review`、`approved`、`rejected` |
| `generation_batch_id` | int nullable FK | 属于哪次 AI 生成批次 |
| `needs_review` | boolean | 内容更新后，该题是否需要管理员复核 |
| `review_reason` | text nullable | 需要复核的原因，例如“关联内容发生大更新” |
| `expires_at` | datetime nullable | 短周期题过期时间，常用于最新必读题 |
| `priority` | int | 抽题优先级，大更新专题题可提高优先级 |

与现有字段关系：

- `status = enabled/disabled` 表示题目是否可被员工端抽取。
- `review_status = approved` 表示题目审核通过。
- 员工端只应抽取 `status = enabled` 且 `review_status = approved` 的题。
- AI 生成的题默认 `status = disabled`、`review_status = pending_review`。

### 6.3 新增 `quiz_generation_batches`

只要引入 AI 出题，就建议新增生成批次表，避免将来无法追踪“这批题怎么来的”。

建议字段：

```text
id
content_id
version_id
update_level
status
model_name
prompt_version
requested_count
generated_count
created_by
created_at
error_message
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `content_id` | 生成题目的来源内容 |
| `version_id` | 生成题目的来源版本 |
| `update_level` | 当次发布更新级别 |
| `status` | `pending`、`completed`、`failed` |
| `model_name` | 使用的模型名称 |
| `prompt_version` | 出题提示词版本 |
| `requested_count` | 请求生成几道题 |
| `generated_count` | 实际生成几道题 |
| `created_by` | 触发生成的管理员 |
| `error_message` | 失败原因 |

作用：

- 方便管理员查看 AI 出题历史。
- 方便排查 AI 生成失败。
- 方便回溯某道题来自哪次提示词、哪次发布。

### 6.4 可选新增 `quiz_sets`

如果要做“大更新专题测验包”，建议新增 `quiz_sets` 和 `quiz_question_set_items`。

`quiz_sets`：

```text
id
title
description
related_content_id
related_version_id
update_level
permission_level
status
expires_at
created_at
```

`quiz_question_set_items`：

```text
quiz_set_id
question_id
sort_order
```

作用：

- 将一批题组织成“消防验收新要求专项测验包”。
- 大更新后员工端可以优先抽取或展示该测验包。
- 后续如果做强制学习，可以复用这个结构。

第一阶段如果想控制复杂度，可以先不做 `quiz_sets`，只通过 `priority` 提高大更新题的抽取权重。

### 6.5 暂不新增员工答题记录表

当前阶段不新增：

```text
quiz_attempts
quiz_attempt_answers
```

原因：

- 当前产品定位仍是“巩固测试”，不是正式考核。
- 不统计员工完成率、得分、排名。
- 不保存员工历史答题明细。

如果未来要做培训闭环、完成率、错题本或强制考核，再新增这两张表。

## 7. 题目状态流转

### 7.1 人工创建题

```text
管理员新建题
  -> source_type = manual
  -> review_status = approved
  -> status 可由管理员选择 enabled/disabled
```

人工题默认可以直接审核通过，因为管理员自行负责题目质量。

### 7.2 AI 生成题

```text
AI 生成候选题
  -> source_type = ai_generated
  -> review_status = pending_review
  -> status = disabled
  -> 管理员审核
    -> 通过：review_status = approved，可启用
    -> 拒绝：review_status = rejected，保持禁用
    -> 编辑后通过：source_type 可保持 ai_assisted
```

员工端不得展示：

- `review_status != approved` 的题。
- `status != enabled` 的题。
- 超过 `expires_at` 的题。
- 当前用户无权限的题。

### 7.3 内容更新导致旧题待复核

中更新或大更新发布后：

```text
查找 related_content_id = 当前内容 的题
  -> 排除已禁用且无需追踪的历史题
  -> 设置 needs_review = true
  -> 设置 review_reason
  -> 管理员逐题处理
```

管理员可处理为：

- 确认仍有效：`needs_review = false`
- 编辑后继续启用：更新题目内容并清除复核标记
- 禁用：`status = disabled`
- 拒绝 AI 候选题：`review_status = rejected`

## 8. 员工端抽题规则

员工端只抽取满足以下条件的题：

```text
status = enabled
review_status = approved
permission_level 在当前用户可见范围内
expires_at 为空或 expires_at > 当前时间
如果绑定内容，则关联内容必须仍是 published 且当前用户可见
```

权限规则沿用现有系统：

- 通用员工只能抽取通用级题。
- 全量员工可以抽取通用级和全量级题。
- 管理员如果访问员工端，也可看到通用级和全量级题。

抽题优先级建议：

1. 未过期的大更新专题题。
2. 最近中更新产生或复核通过的题。
3. 普通启用题。

第一阶段仍可保持当前 5 到 10 道题的简单抽取逻辑，只增加过滤条件和优先级。

## 9. 后台页面建议

### 9.1 内容发布页

发布确认时增加：

- 本次更新级别。
- 本次变更摘要。
- AI 建议的更新级别与原因。
- 预计题库动作。

示例：

```text
本次更新级别：大更新
题库动作：生成专题测验候选题，并复核关联旧题
```

### 9.2 测验题管理页

题目列表建议增加：

- 来源：人工 / AI 生成 / AI 辅助。
- 审核状态。
- 是否待复核。
- 关联内容版本。
- 过期时间。
- 生成批次。

筛选建议增加：

- 待审核。
- 待复核。
- AI 生成。
- 大更新相关。
- 已过期。

### 9.3 AI 生成候选题入口

入口可以放在两个位置：

1. 内容发布结果页：发布后生成候选题。
2. 测验题管理页：选择内容版本后手动生成。

第一阶段建议先做内容发布后的生成入口，流程更自然。

## 10. 异常与边界处理

### 10.1 AI 生成失败

处理规则：

- 内容发布不回滚。
- 记录 `quiz_generation_batches.status = failed`。
- 记录错误原因。
- 后台显示“题目生成失败，可重试”。

### 10.2 内容下线

内容下线后：

- 员工端不应展示绑定该内容且无法访问来源的题目。
- 后台仍可保留题目用于历史追踪。
- 管理员可批量禁用这些题。

### 10.3 内容权限变化

如果内容从通用级改为全量级并重新发布：

- 新版本绑定的题目应使用新权限。
- 旧题需要复核权限是否仍正确。
- 员工端必须以后端权限过滤为准。

### 10.4 小更新误标为大更新

允许管理员在发布前修改更新级别。

如果已经生成候选题：

- 候选题可以保留为待审核。
- 管理员可以批量拒绝或删除。

### 10.5 大更新误标为小更新

管理员后续应可以在版本详情中补触发题库动作：

```text
版本详情 -> 触发题目复核 / 生成候选题
```

这样即使发布时漏选，也能补救。

## 11. 分阶段实施建议

### 第一阶段：稳态增强

目标：不做员工答题记录，只增强题库与内容版本的关系。

建议实现：

- `content_versions` 增加 `update_level`、`change_summary`、`quiz_action`。
- `quiz_questions` 增加 `related_version_id`、`source_type`、`review_status`、`needs_review`、`review_reason`。
- 员工端只抽取审核通过且启用的题。
- 中/大更新后标记关联旧题待复核。

### 第二阶段：AI 生成候选题

建议实现：

- 新增 `quiz_generation_batches`。
- 内容发布后支持生成候选题。
- AI 候选题默认待审核、禁用。
- 管理员审核通过后启用。

### 第三阶段：大更新专题测验包

建议实现：

- 新增 `quiz_sets` 和 `quiz_question_set_items`。
- 大更新创建专题测验包。
- 员工端优先抽取专题题。
- 暂不记录员工完成情况。

### 第四阶段：培训闭环

只有当业务明确需要考核和统计时再做：

- `quiz_attempts`
- `quiz_attempt_answers`
- 完成率
- 错题本
- 管理员统计报表

## 12. 不做事项

当前阶段明确不做：

- AI 自动启用题目。
- AI 自由发挥生成超出原文的题目。
- 员工答题历史记录。
- 员工分数排名。
- 强制考试。
- 复杂考试组卷策略。
- 多岗位细分题库。
- 题目对话式讲解。

这些能力以后可以扩展，但不进入本轮边界。

## 13. 验收标准

后续实现应满足：

- 内容版本号和更新级别同时存在，互不覆盖。
- 小更新不会强制影响题库。
- 中更新会标记关联旧题待复核。
- 大更新会建议生成候选题或专题测验包。
- AI 生成题默认不能直接进入员工端。
- 管理员审核后，题目才能启用。
- 员工端只看到当前权限内、已审核、已启用、未过期的题。
- 内容下线或权限变化后，题目不会绕过内容权限暴露给员工。
- 后台可以追踪题目来源、关联内容、关联版本和生成批次。
