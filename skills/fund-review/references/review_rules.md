# Review Rules

## Source Boundary

Only review text supplied in the current `numbered_text` input. Do not use previous conversations, sample text, examples, or rule descriptions as evidence.

Before reporting an issue, verify:

- the referenced `[p-s]` marker exists in `numbered_text`
- `excerpt` is an exact substring of that sentence
- `global_s_id` starts with the current `doc_id`

## Compliance Issues

Report every match from these categories. Compliance issues do not use the typo rule's "skip if unsure" standard.

### 保本承诺

Severity: `high`

Examples of risky wording: `保本`, `不亏损`, `本金无忧`, `绝对安全`, `保证本金`, `兜底`.

### 收益承诺

Severity: `high`

Examples of risky wording: `保收益`, `保证收益`, `最低收益 X%`, `锁定收益`, `稳赚`, `稳赚不赔`, `躺赚`, `包赚`.

### 确定性预测

Severity: `medium` or `high`

Examples of risky wording: `一定上涨`, `必涨`, `肯定盈利`, `将会大涨`, `未来 N 个月必定上涨 X%`, `确定性机会`, `板上钉钉`.

### 业绩排名

Severity: `medium`

Examples of risky wording: `行业第一`, `排名最高`, `收益率最高`, `跑赢所有同类`, `业内最优`.

Also report return-rate promotion without a clear time range or benchmark, such as `年化 30%` when the context omits the period or comparison basis.

### 推荐买入

Severity: `medium`

Examples of risky wording: `建议购买`, `推荐买入`, `赶紧上车`, `不买就亏了`, `现在是最佳时机`.

### 其它诱导

Severity: `low` or `medium`

Report overly absolute or risk-obscuring wording such as `绝对`, `百分百`, `毫无风险`, `闭眼买`, `无脑买`.

## Writing Errors

Use category `错别字`. Only report a writing error when highly confident.

Focus on:

- homophone misuse where context clearly requires another character
- visually similar character misuse
- missing or duplicated characters that make the sentence ungrammatical
- incomplete year formats with fewer than four digits before `年`
- meaningless repeated character sequences with three or more identical letters or characters
- number and unit formatting errors such as `1 .5%`
- obvious punctuation errors such as `。。` or English punctuation inside Chinese prose

Severity calibration:

- default writing error: `low`
- incomplete year format: `medium`
- repeated noise inside meaningful content: `medium`
- repeated noise only at sentence end: `low`
- severe ambiguity caused by a typo: `medium`

For typo comments, use an explicit `X 应改为 Y` suggestion.

## False-positive Whitelist

Do not report:

- accepted financial terms and abbreviations such as `权益类`, `久期`, `Beta`, `Alpha`, `α`, `β`, `PE`, `PB`, `PEG`, `ROE`, `CAGR`, `Q1`, `Q2`, `AH 股`, `北向资金`, `险资`, `LP/GP`
- names of people, funds, products, companies, or indexes
- harmless numeric style differences such as `0.3%` vs `0.30%`
- classical or formal wording such as `之于`, `于此`, `殆`, `乃`, `兹`

Repeated meaningless sequences with three or more identical characters are not protected by the abbreviation whitelist.

## JSON Contract

Return JSON only. Do not include Markdown fences, comments, or explanatory text.

Required top-level fields:

- `summary`: one sentence, no more than 60 Chinese characters; do not repeat issue details here
- `issues`: array of issue objects

Each issue requires:

- `global_s_id`: `<doc_id>-<p_index>-<s_index>`
- `excerpt`: exact original sentence text without the `[p-s]` marker
- `category`: one of `保本承诺`, `收益承诺`, `确定性预测`, `业绩排名`, `推荐买入`, `其它诱导`, `错别字`
- `severity`: one of `low`, `medium`, `high`
- `comment`: actionable review comment and revision suggestion

