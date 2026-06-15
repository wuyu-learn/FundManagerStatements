import os
import re
import json
import asyncio
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

from openai import AsyncOpenAI
from mcp import ClientSession
from mcp.client.sse import sse_client
from .event_stream import EventEmitter, EventType

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001/sse")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

openai_client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
)

REACT_SYSTEM_PROMPT = """
你是一个智能审核 Agent，负责编排 Skill 工具完成基金经理评述的合规审核。

## ⛔ 最高优先级 - 数据来源硬约束（必读）

你和你调用的所有 Skill 工具，**只能且仅能**对**当前用户在本会话中提交的 numbered_text 文本**进行分析与引用。

具体禁令：
- ❌ 严禁套用任何历史会话或之前对话的内容
- ❌ 严禁把任何 Skill prompt 里的「示例 / 例如 / e.g.」后面的文本当作命中证据 —— 那些只是规则描述
- ❌ 严禁凭空捏造未在 numbered_text 里字面出现的违规、错别字或乱码
- ✅ 任何引用必须能在当前 numbered_text 中**字面定位**

## 可用工具

{tools_description}

## 任务流程
1. 看到用户输入的带 [p-s] 编号的评述后，**第一步必须调用 Review 工具**，把完整的 numbered_text 和 doc_id 都传过去
2. 拿到 Review 返回的 issues 数组后，**第二步调 final_answer 写一份「合规定性综述」**
3. 同一份文本不需要循环多次 Review，审一次就够

## 单次响应格式
每次只返回**一个** JSON 对象。

调用工具时：
{{
  "thought": "我的思考",
  "action": "tool_name",
  "action_input": {{ "参数名": "值" }}
}}

完成时（final_answer）：
{{
  "thought": "已完成审核",
  "action": "final_answer",
  "action_input": {{"answer": "<合规定性综述文本>"}}
}}

## ⚠️ 严格的「数据职责边界」（必读，违反即视为输出错误）

前端有两个**互相独立**的显示区，你**绝对不能把它们的数据搞混**：

### 🅰️ 第 2 栏「审核反馈」= Review Tool 的 issues 数组
- 所有「单句违规」「位置」「修改建议」**必须**通过 Review 工具的 JSON 结构化输出
- Review 是这类数据的**唯一**来源
- 不允许你自己在 thought / final_answer 里凭空生成 issue

### 🅱️ 第 3 栏「完整审核报告」= final_answer 的纯文本
- 仅写**通篇定性综述**，专家口吻、宏观判断
- 必须包含四块：
  1. **整体合规情况**（合规 / 局部存在风险 / 显著违规）
  2. **主要违规模块汇总**（如「保本承诺类」「确定性预测类」「文字录入类」，仅说类别，不展开具体句子）
  3. **综合风险等级**（低 / 中 / 高，配一句话理由）
  4. **整改方向**（宏观建议，如「建议重新表述收益相关句子」「建议全文做一次错别字通读」）
- 控制在 200-400 字，**禁止超长罗列**

### ⛔ final_answer 中**严禁**出现的内容
- ⛔ 复述具体单句违规（如「[1-2] 中存在保本保收益违规」）
- ⛔ 引用任何 `[p-s]` 编号 或 `global_s_id`
- ⛔ 逐条列举 issue（如「问题1：...；问题2：...」）
- ⛔ 列举具体错别字（如「'基晶' 应改为 '基金'」）

**这些细节属于 🅰️ Review 工具的领地**。Review 已经把它们结构化推送给前端 col 2 渲染了；你在 col 3 重复一遍，就是数据冗余 + 职责越界 + 用户看到精神分裂的两栏。

### ✅ final_answer 正确范例
> "本次评述整体存在**显著合规风险**。主要问题集中在两个模块：(1) **过度业务承诺**，涉及保本与绝对收益类表述；(2) **文字录入疏漏**，包括同音字混用。综合风险等级：**高**，原因是出现了「保本」「绝对收益」等监管明令禁止的措辞。建议优先修订所有涉及收益承诺的句子，并对全文做一次错别字通读，再次提交审核。"

### ❌ final_answer 错误范例（绝不要这样写）
> "问题1：[1-2] 中存在保本保收益违规；问题2：[2-1] 中 '基晶' 应改为 '基金'；问题3：..."
> ↑ 这些是 Review 工具该输出的结构化数据，**不该**出现在 final_answer 文本里

## 其它约束
1. `action_input` 必须是 JSON 对象（字典），参数名严格匹配工具签名
2. 每次只返回一个 JSON，无任何额外文字、代码围栏或注释
3. 调 Review **之前**，不要先在 thought 里分析具体违规 —— 那是 Review 的活，把它留给 Review 去干
"""


# 匹配 LLM 偶尔会偷懒输出的「短形式」global_s_id，如 "1-2"（缺 doc_id 前缀）
_SHORT_SID_RE = re.compile(r"^\d+-\d+$")
# Fix 2: 匹配「前导 dash」幻觉 ID，如 "-1-2" / "--1-2"
# —— 通常是 Review prompt 里 {{ doc_id }} 渲染为空时拼接出的产物
_LEADING_DASH_SID_RE = re.compile(r"^-+(\d+-\d+)$")


class AgentOrchestrator:
    def __init__(self, emitter: EventEmitter, doc: Optional[dict] = None):
        self.emitter = emitter
        # P2/P3：保留文档树用于在 Tool 输出里校验 global_s_id 是否真的存在
        self.doc = doc
        self._valid_sids: set[str] = set()
        if doc:
            for p in doc.get("paragraphs", []) or []:
                for s in p.get("sentences", []) or []:
                    sid = s.get("global_s_id")
                    if sid:
                        self._valid_sids.add(sid)

    async def _validate_skill_observation(self, observation: str) -> tuple[str, Optional[dict]]:
        """
        若 observation 是 JSON 且含 issues[].global_s_id，校验每个 ID 是否在文档树中存在：
        - 短形式（"1-2"）→ 自动补 doc_id 前缀
        - 完全不存在 → global_s_id 置为 None，加 _validation_warning 说明
        返回 (可能被修正过的 observation 字符串, 解析后的 dict 或 None)。
        第二个返回值方便调用方判断要不要 emit REVIEW_ISSUES。
        """
        try:
            data = json.loads(observation)
        except (json.JSONDecodeError, TypeError):
            return observation, None
        if not isinstance(data, dict):
            return observation, None

        issues = data.get("issues")
        if not isinstance(issues, list) or not self._valid_sids or not self.doc:
            return observation, data

        doc_id = self.doc.get("doc_id")
        hallucinated: list[str] = []
        fixed_short = 0

        for issue in issues:
            if not isinstance(issue, dict):
                continue
            sid = issue.get("global_s_id")
            if not isinstance(sid, str) or not sid:
                continue
            if sid in self._valid_sids:
                continue
            # 尝试 1：短形式 "p-s" → 补 doc_id 前缀
            if doc_id and _SHORT_SID_RE.match(sid):
                candidate = f"{doc_id}-{sid}"
                if candidate in self._valid_sids:
                    issue["global_s_id"] = candidate
                    fixed_short += 1
                    continue
            # Fix 2 - 尝试 2：前导 dash 形式 "-1-2" / "--1-2"（doc_id 渲染为空导致），剥掉前导 dash 后补 prefix
            m = _LEADING_DASH_SID_RE.match(sid)
            if doc_id and m:
                candidate = f"{doc_id}-{m.group(1)}"
                if candidate in self._valid_sids:
                    issue["global_s_id"] = candidate
                    fixed_short += 1
                    continue
            # 兜底：标记为幻觉
            hallucinated.append(sid)
            issue["_validation_warning"] = f"global_s_id 不在文档树中: {sid}"
            issue["global_s_id"] = None

        if hallucinated or fixed_short:
            parts = []
            if fixed_short:
                parts.append(f"自动补全 {fixed_short} 个短 ID")
            if hallucinated:
                sample = ", ".join(hallucinated[:3])
                more = "..." if len(hallucinated) > 3 else ""
                parts.append(f"剔除 {len(hallucinated)} 个幻觉 ID ({sample}{more})")
            # 仅 stdout 日志，不 emit ERROR —— 否则前端 error 监听会误判为致命错并提前关流
            print(f"[orchestrator] Review 输出校验: {'；'.join(parts)}", flush=True)
            return json.dumps(data, ensure_ascii=False), data

        return observation, data

    async def run(self, user_input: str):
        try:
            async with sse_client(MCP_SERVER_URL) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    tools_result = await session.list_tools()
                    tools = tools_result.tools

                    # 把每个工具的参数 schema 也喂给 LLM，避免它瞎传参
                    def _fmt_tool(t):
                        schema = getattr(t, "inputSchema", None) or {}
                        props = schema.get("properties", {}) or {}
                        required = set(schema.get("required", []) or [])
                        if props:
                            param_lines = []
                            for name, info in props.items():
                                ptype = info.get("type", "any")
                                req = "必填" if name in required else "可选"
                                desc = info.get("description", "")
                                param_lines.append(
                                    f'  - "{name}" ({ptype}, {req}): {desc}'
                                )
                            param_text = "\n".join(param_lines)
                        else:
                            param_text = "  (无参数)"
                        return f"### {t.name}\n描述: {t.description}\n参数:\n{param_text}"

                    tools_description = "\n\n".join(_fmt_tool(t) for t in tools)

                    messages = [
                        {"role": "system", "content": REACT_SYSTEM_PROMPT.format(
                            tools_description=tools_description
                        )},
                        {"role": "user", "content": user_input},
                    ]

                    for iteration in range(10):
                        response = await openai_client.chat.completions.create(
                            model=LLM_MODEL,
                            messages=messages,
                            response_format={"type": "json_object"},
                        )
                        raw = response.choices[0].message.content

                        try:
                            parsed = json.loads(raw)
                        except json.JSONDecodeError:
                            await self.emitter.emit(EventType.ERROR, {
                                "message": "LLM 返回格式错误", "raw": raw
                            })
                            break

                        thought = parsed.get("thought", "")
                        action = parsed.get("action", "")
                        action_input = parsed.get("action_input", {})

                        # 防御：LLM 偶尔会把单参数工具的 input 直接当成字符串传
                        # 此处自动包成 {第一个required参数名: 字符串}，避免 Skill 调用直接挂掉
                        if isinstance(action_input, str) and action and action != "final_answer":
                            tool_def = next((t for t in tools if t.name == action), None)
                            if tool_def is not None:
                                schema = getattr(tool_def, "inputSchema", None) or {}
                                required = schema.get("required", []) or []
                                if required:
                                    action_input = {required[0]: action_input}
                                else:
                                    props = list((schema.get("properties", {}) or {}).keys())
                                    if props:
                                        action_input = {props[0]: action_input}
                                    else:
                                        action_input = {"input": action_input}

                        # Fix 1: Orchestrator 持有 doc 时强制把 doc_id 注入到 required 含 "doc_id" 的 Tool 调用
                        # 防止 LLM 偷懒只填 numbered_text 导致 Skill prompt {{ doc_id }} 渲染为空 → 吐出 "-1-1" 这种废 ID
                        if (
                            self.doc
                            and isinstance(action_input, dict)
                            and action
                            and action != "final_answer"
                        ):
                            tool_def = next((t for t in tools if t.name == action), None)
                            if tool_def is not None:
                                schema = getattr(tool_def, "inputSchema", None) or {}
                                required = schema.get("required", []) or []
                                if "doc_id" in required and not action_input.get("doc_id"):
                                    action_input["doc_id"] = self.doc["doc_id"]
                                    print(
                                        f"[orchestrator] 自动补齐 doc_id={self.doc['doc_id']} 给 Tool: {action}",
                                        flush=True,
                                    )

                        await self.emitter.emit(EventType.THOUGHT, {
                            "content": thought,
                            "iteration": iteration + 1
                        })

                        if action == "final_answer":
                            await self.emitter.emit(EventType.FINAL_ANSWER, {
                                "content": action_input.get("answer", "")
                            })
                            break

                        await self.emitter.emit(EventType.ACTION, {
                            "tool": action,
                            "input": action_input,
                            "iteration": iteration + 1
                        })
                        await self.emitter.emit(EventType.SKILL_START, {"skill": action})

                        # 🔬 诊断日志 1/2：Tool 调用入参（看 Agent 传给 Review 的 numbered_text 完整性）
                        try:
                            _input_dump = json.dumps(action_input, ensure_ascii=False)
                        except Exception:
                            _input_dump = repr(action_input)
                        print(
                            f"[orchestrator] → Tool: {action} | input ({len(_input_dump)} chars): {_input_dump[:800]}",
                            flush=True,
                        )

                        try:
                            result = await session.call_tool(action, action_input)
                            observation = result.content[0].text if result.content else "{}"
                        except Exception as e:
                            observation = json.dumps({"error": str(e)})
                            await self.emitter.emit(EventType.ERROR, {
                                "message": f"Tool 调用失败: {e}"
                            })

                        # 🔬 诊断日志 2/2：Tool 原始返回（看 Review 的 LLM 到底吐了什么 issues/summary）
                        print(
                            f"[orchestrator] ← Tool: {action} | observation ({len(observation)} chars): {observation[:1500]}",
                            flush=True,
                        )

                        # P3 防御性校验：如果 Tool 输出含 issues[].global_s_id，校验并可能修正
                        observation, parsed_obs = await self._validate_skill_observation(observation)

                        # P4：若 Tool 输出是 Review 风格（dict 且含 issues 或 summary），
                        # 单独 emit REVIEW_ISSUES 给前端中栏卡片立刻渲染
                        if isinstance(parsed_obs, dict) and (
                            "issues" in parsed_obs or "summary" in parsed_obs
                        ):
                            issues_list = parsed_obs.get("issues", [])
                            if not isinstance(issues_list, list):
                                issues_list = []
                            summary_text = parsed_obs.get("summary", "")
                            if not isinstance(summary_text, str):
                                summary_text = str(summary_text)
                            await self.emitter.emit(EventType.REVIEW_ISSUES, {
                                "tool": action,
                                "issues": issues_list,
                                "summary": summary_text,
                            })

                        await self.emitter.emit(EventType.SKILL_END, {
                            "skill": action,
                            "output_preview": observation[:300]
                        })
                        await self.emitter.emit(EventType.OBSERVATION, {
                            "tool": action,
                            "content": observation,
                            "iteration": iteration + 1
                        })

                        messages.append({"role": "assistant", "content": raw})
                        messages.append({"role": "user", "content": f"Observation: {observation}"})

                    else:
                        await self.emitter.emit(EventType.ERROR, {"message": "已达到最大迭代次数"})
        except asyncio.CancelledError:
            # 用户主动取消：通知前端，但不 re-raise —— 让 fire-and-forget 的 task 自然终止
            # 避免日志里冒 "Task exception was never retrieved" 或赤裸的 CancelledError 噪音
            await self.emitter.emit(EventType.ERROR, {
                "message": "已被用户取消"
            })
        except Exception as e:
            # MCP 连接 / OpenAI API / 其它任何未捕获异常，都立刻通报前端
            await self.emitter.emit(EventType.ERROR, {
                "message": f"Agent 运行失败: {type(e).__name__}: {str(e)[:300]}"
            })
        finally:
            # 不论成功失败都必须发 __DONE__ 让 SSE 流关闭，否则前端会一直挂着等
            await self.emitter.emit(EventType.FINAL_ANSWER, {"content": "__DONE__"})
