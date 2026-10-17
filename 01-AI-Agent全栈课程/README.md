# AI Agent 全栈课程

> **来源**：[callous-0923/agent-study](https://github.com/callous-0923/agent-study) · 520 ⭐ · **MIT License**
> 37 章（Ch0–Ch36）7 层递进，每章附可运行 Python 源码
> 本目录为**本地离线副本**，已做链接改写（见文末「本地化改动」）

---

## 怎么读

**方式一：学习台（推荐）**
双击桌面「StudyAI 学习台」→ 左侧目录进 `01-AI-Agent全栈课程` → 点 `index.html`。
课程自带侧栏与上下章导航，直接在页面里翻页。

**方式二：直接打开**
双击 `index.html` 用浏览器看。全站零外部依赖，**断网可用**。

---

## 课程结构（7 层 / 37 章）


### 第1层：Agent 理论基础 (Ch0-3)

| 章 | 标题 | 技术要点 | 源码 |
|---|---|---|---|
| **Ch0** | [课程概览与环境搭建](chapter_00_overview/00_course_overview.html) | 学习路线图 · 依赖安装 · API Key 配置 | [.py](chapter_00_overview/00_course_overview.py) |
| **Ch1** | [第一个 Agent](chapter_01_fundamentals/01_hello_agent.html) | 裸写 ReAct 循环 · Function Calling 原理 | [.py](chapter_01_fundamentals/01_hello_agent.py) |
| **Ch2** | [Agent 核心组件](chapter_02_components/02_agent_components.html) | 规划器 · 记忆系统 · 工具设计黄金法则 | [.py](chapter_02_components/02_agent_components.py) |
| **Ch3** | [Agent 类型分类](chapter_03_types/03_agent_types.html) | ReAct · Plan-Execute · Reflexion 对比 | [.py](chapter_03_types/03_agent_types.py) |

### 第2层：工程实践与框架 (Ch4-7)

| 章 | 标题 | 技术要点 | 源码 |
|---|---|---|---|
| **Ch4** | [主流框架实战](chapter_04_frameworks/04_frameworks.html) | LangChain Agent · LangGraph 状态机 | [.py](chapter_04_frameworks/04_frameworks.py) |
| **Ch5** | [多智能体系统](chapter_05_multi_agent/05_multi_agent.html) | Writer+Reviewer 协作 · crewAI 风格 | [.py](chapter_05_multi_agent/05_multi_agent.py) |
| **Ch6** | [评估与测试](chapter_06_evaluation/06_evaluation.html) | 评测框架 · LLM-as-Judge · 生产 Checklist | [.py](chapter_06_evaluation/06_evaluation.py) |
| **Ch7** | [求职面试准备](chapter_07_interview/07_interview_prep.html) | 20 道高频面试题 · 项目指南 · 面试流程 | [.py](chapter_07_interview/07_interview_prep.py) |

### 第3层：深度技术剖析 (Ch8-12)

| 章 | 标题 | 技术要点 | 源码 |
|---|---|---|---|
| **Ch8** | [Claude Code 架构](chapter_08_claude_code/08_claude_code_architecture.html) | nO 主循环 · h2A Steering · 上下文压缩 · SubAgent | [.py](chapter_08_claude_code/08_claude_code_architecture.py) |
| **Ch9** | [RAG 深度解析](chapter_09_rag_deepdive/09_rag_deepdive.html) | Chunk策略·Embedding选型·RRF·Cross-Encoder·生产失败模式 | [.py](chapter_09_rag_deepdive/09_rag_deepdive.py) |
| **Ch10** | [MCP 协议详解](chapter_10_mcp/10_mcp_deepdive.html) | 2026-07-28 无状态核心 · 路由 · MRTR · 缓存 | [.py](chapter_10_mcp/10_mcp_deepdive.py) |
| **Ch11** | [Tool Calling 底层](chapter_11_tool_calling/11_tool_calling_deepdive.html) | OpenAI/Anthropic · Tool Search/PTC · Strict | [.py](chapter_11_tool_calling/11_tool_calling_deepdive.py) |
| **Ch12** | [Agent 生产基础设施](chapter_12_infrastructure/12_infrastructure.html) | OpenClaw 架构 · Harness · 生产化 Checklist | [.py](chapter_12_infrastructure/12_infrastructure.py) |

### 第4层：工程化与前沿 (Ch13-18)

| 章 | 标题 | 技术要点 | 源码 |
|---|---|---|---|
| **Ch13** | [FastAPI 服务化](chapter_13_fastapi/13_fastapi_agent_service.html) | REST/SSE/WebSocket · 可运行 UI · Background/Webhook | [.py](chapter_13_fastapi/13_fastapi_agent_service.py) |
| **Ch14** | [SQLite 持久化](chapter_14_sqlite/14_sqlite_agent_storage.html) | 5 表 Schema · WAL 模式 · 审计查询 | [.py](chapter_14_sqlite/14_sqlite_agent_storage.py) |
| **Ch15** | [Google A2A 协议](chapter_15_a2a/15_a2a_protocol.html) | AgentCard · Task · Artifact · Multi-Agent 协作 | [.py](chapter_15_a2a/15_a2a_protocol.py) |
| **Ch16** | [MemGPT/Letta 记忆](chapter_16_memgpt/16_memgpt_letta.html) | Core Memory · Heartbeat · Sleep-Time Compute | [.py](chapter_16_memgpt/16_memgpt_letta.py) |
| **Ch17** | [Computer Use](chapter_17_computer_use/17_computer_use.html) | Screenshot-Action Loop · 坐标计算 · 安全沙箱 | [.py](chapter_17_computer_use/17_computer_use.py) |
| **Ch18** | [Agent 安全与护栏](chapter_18_security/18_agent_security.html) | Prompt Injection · 权限分级 · 4层防御 | [.py](chapter_18_security/18_agent_security.py) |

### 第5层：高级架构与优化 (Ch19-24)

| 章 | 标题 | 技术要点 | 源码 |
|---|---|---|---|
| **Ch19** | [Agentic Workflow 设计模式](chapter_19_workflow_patterns/19_workflow_patterns.html) | Reflection · Routing · Orchestrator-Worker 等 7 种 | [.py](chapter_19_workflow_patterns/19_workflow_patterns.py) |
| **Ch20** | [Context Engineering](chapter_20_context_engineering/20_context_engineering.html) | Context Rot · 预算管理 · XML 结构化 Prompt | [.py](chapter_20_context_engineering/20_context_engineering.py) |
| **Ch21** | [Streaming & 实时架构](chapter_21_streaming/21_streaming_architecture.html) | EventBus · 断线恢复 · 人工审批 · Realtime | [.py](chapter_21_streaming/21_streaming_architecture.py) |
| **Ch22** | [DSPy 自动优化](chapter_22_dspy/22_dspy.html) | Signature→Module→Optimizer · 与 LangChain 互补 | [.py](chapter_22_dspy/22_dspy.py) |
| **Ch23** | [代码 Agent 架构横评](chapter_23_code_agents/23_code_agents.html) | CodeAct · ACI · Plan-Execute · SWE-bench | [.py](chapter_23_code_agents/23_code_agents.py) |
| **Ch24** | [Agent 可观测性](chapter_24_observability/24_observability.html) | Tracing Span 树 · LangSmith vs LangFuse | [.py](chapter_24_observability/24_observability.py) |

### 第6层：基础能力补强 (Ch25-28)

| 章 | 标题 | 技术要点 | 源码 |
|---|---|---|---|
| **Ch25** | [向量数据库选型](chapter_25_vectordb/25_vectordb.html) | Chroma · Pinecone · Milvus · Qdrant | [.py](chapter_25_vectordb/25_vectordb.py) |
| **Ch26** | [模型路由策略](chapter_26_model_routing/26_model_routing.html) | Threshold · Cascade · Semantic · Cost-Aware | [.py](chapter_26_model_routing/26_model_routing.py) |
| **Ch27** | [Agent Prompt 工程](chapter_27_prompt_eng/27_prompt_engineering.html) | System Prompt 6 模块模板 · 工具描述评分卡 | [.py](chapter_27_prompt_eng/27_prompt_engineering.py) |
| **Ch28** | [语义缓存与 Token 优化](chapter_28_cache/28_cache.html) | 三级缓存 · Token 预算管理 | [.py](chapter_28_cache/28_cache.py) |

### 第7层：专家级进阶 (Ch29-36)

| 章 | 标题 | 技术要点 | 源码 |
|---|---|---|---|
| **Ch29** | [Multi-Modal Agent](chapter_29_multimodal/29_multimodal.html) | 视觉+文本联合推理 · Token 预算 | [.py](chapter_29_multimodal/29_multimodal.py) |
| **Ch30** | [Agent 可靠性工程](chapter_30_reliability/30_reliability.html) | 熔断器 · 退避重试 · 幂等 · 降级 | [.py](chapter_30_reliability/30_reliability.py) |
| **Ch31** | [Agent 评测体系深度](chapter_31_benchmarks/31_benchmarks.html) | GAIA · AgentBench · WebArena · ClawBench · tau-bench · SWE-bench | [.py](chapter_31_benchmarks/31_benchmarks.py) |
| **Ch32** | [Self-Improving Agent](chapter_32_self_improving/32_self_improving.html) | Bad Case 收集→自动改 Prompt→评测验证 | [.py](chapter_32_self_improving/32_self_improving.py) |
| **Ch33** | [Prompt Caching & 推理优化](chapter_33_prompt_cache/33_prompt_cache.html) | Anthropic Cache · KV共享 · 推测解码 | [.py](chapter_33_prompt_cache/33_prompt_cache.py) |
| **Ch34** | [模型微调 for Function Calling](chapter_34_finetune/34_finetune.html) | LoRA · 微调数据准备 · 成本收益 | [.py](chapter_34_finetune/34_finetune.py) |
| **Ch35** | [数据飞轮](chapter_35_data_flywheel/35_data_flywheel.html) | 交互采集→Bad Case识别→自动触发改进 | [.py](chapter_35_data_flywheel/35_data_flywheel.py) |
| **Ch36** | [Agent 纵深安全](chapter_36_defense/36_defense.html) | Canary Token · 分层隔离 · 行为沙箱 | [.py](chapter_36_defense/36_defense.py) |

---

## 本地化改动

为了让站点能**完全离线**运行，导入时做了三处修改：

| 改动 | 规模 | 原因 |
|---|---|---|
| 绝对 URL 改写为相对路径 | 1,661 处 | 原文侧栏/上下章链接硬编码指向 `callous-0923.github.io`，不改则断网失效 |
| 移除 busuanzi 统计脚本 | 38 页 | 外部 CDN 的访问量统计，本地无意义 |
| 移除访问量徽章（含 CSS） | 38 页 | 同上 |

**校验结果**：站内导航链接 **1,698 个全部可解析**（另有 2 处 `/docs` 在 `<pre>` 代码块内，属 FastAPI 示例，非导航）。

内容本身**未做任何改动**。

---

## 许可

本课程采用 **MIT License**，可自由使用、修改、分发（需保留版权声明）。
许可证全文见 [LICENSE](LICENSE)。版权归原作者 [callous-0923](https://github.com/callous-0923) 所有。

---

## 环境准备

```powershell
# 课程根目录有 requirements.txt
cd C:\StudyAI\01-AI-Agent全栈课程
python -m pip install -r requirements.txt

# 配置 API Key：在课程根目录建 .env
#   OPENAI_API_KEY=sk-xxxxxxxx
#   OPENAI_BASE_URL=https://api.deepseek.com/v1   # 或用国产模型
#   LLM_MODEL=deepseek-chat
```

> Ch8 之后的章节大多只用 Python 标准库（`sqlite3` / `asyncio` / `hashlib` / `json`），
> 不装依赖也能读代码。只有 Ch1–5 需要 `openai`、`langchain`、`langgraph`。

---

## 学习建议（摘自课程 Ch0）

| 你的情况 | 建议路径 |
|---|---|
| 新手入门 | 按 Ch0 → Ch36 顺序，每章 1–2 小时 |
| 有基础 | 直接跳 Ch8 开始深度技术 |
| 面试突击 | Ch7 面试20问 + Ch8 Claude Code + Ch9 RAG + Ch10 MCP + Ch11 ToolCall + Ch15 A2A + Ch18 安全 + Ch19 Workflow |
| 构建产品 | Ch13 FastAPI + Ch14 SQLite + Ch24 可观测 + Ch26 模型路由 + Ch28 语义缓存 |
| 降本增效 | Ch26 路由 + Ch28 缓存 + Ch33 Prompt Cache |
