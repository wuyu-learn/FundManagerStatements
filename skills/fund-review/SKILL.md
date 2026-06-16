---
name: fund-review
description: 审核带句子编号的基金经理中文评述，识别过度业务承诺和确定性文字错误，保留句级 ID 并返回结构化 JSON。
---

# 基金评述审核

当用户要求审查、审核、校验基金经理评述、基金定期报告评述、投研观点或类似对外披露文本时，使用这个技能。若输入文本已包含 `[p-s]` 形式的句子编号，应优先按本技能处理。

## 工作流程

1. 确认输入包含 `doc_id` 和 `numbered_text`；每个被审核句子都必须带有 `[p_index-s_index]` 标记。
2. 如果输入还是原始评述文本，先使用 `scripts/splitter.py` 生成 `doc_id`、文档树和 `numbered_text`。
3. 阅读 `references/review_rules.md`，获取详细合规分类、错别字规则、误报白名单和输出契约。
4. 只审核当前 `numbered_text` 中实际出现的文本。提示词或参考文档里的示例只能作为规则说明，不能作为命中证据。
5. 只返回 JSON，顶层必须包含 `summary` 和 `issues`。
6. 每条问题的 `global_s_id` 必须写成 `<doc_id>-<p_index>-<s_index>`；`excerpt` 必须逐字匹配对应句子的原文，且不包含 `[p-s]` 编号。
7. 需要在主链路中校验 `global_s_id` 时，使用 `scripts/review_observation_validator.py`。
8. 需要离线或命令行校验完整 JSON 输出时，使用 `scripts/validate_review_output.py`。

## 输出格式

```json
{
  "summary": "60字以内的一句话整体结论",
  "issues": [
    {
      "global_s_id": "doc_xxx-1-2",
      "excerpt": "命中问题的原句",
      "category": "保本承诺",
      "severity": "high",
      "comment": "具体审核意见与修改建议"
    }
  ]
}
```

`category` 只能使用以下值：`保本承诺`、`收益承诺`、`确定性预测`、`业绩排名`、`推荐买入`、`其它诱导`、`错别字`。
`severity` 只能使用以下值：`low`、`medium`、`high`。

如果没有发现问题，返回：

```json
{"summary":"本段评述未发现过度业务承诺与错别字，措辞规范。","issues":[]}
```
