---
name: example_skill
description: 这是一个示例 Skill，用于展示 Skill 文件的标准格式
input_schema:
  type: object
  properties:
    content:
      type: string
      description: 输入内容
  required:
    - content
output_schema:
  type: object
  properties:
    result:
      type: string
      description: 输出结果
---

<!-- Prompt 内容待填充 -->
