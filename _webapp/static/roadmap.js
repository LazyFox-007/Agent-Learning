/* =====================================================================
   StudyAI 学习路线数据
   由 _webapp/_build/gen-roadmap.js 自动生成，请勿手改
   生成时间: 2026-10-14 12:34:05
   内容: AI Agent 全栈课程 · 7 层 / 37 章
   ===================================================================== */
window.ROADMAP = {
  "courses": [
    {
      "org": "callous-0923",
      "badge": "简体中文",
      "star": true,
      "name": "AI Agent 全栈课程",
      "repo": "agent-study",
      "lessons": 37,
      "level": "入门 → 专家",
      "desc": "从 ReAct 循环裸写开始，经 Claude Code 架构逆向、MCP / A2A 协议、RAG 深度、Agentic Workflow、可观测性，直到纵深安全 —— 37 章全部配可运行 Python 源码。",
      "note": "MIT License · 已本地化（1,661 处链接改写为相对路径，可完全离线阅读）",
      "entry": "01-AI-Agent全栈课程/index.html",
      "dir": "01-AI-Agent全栈课程",
      "repoUrl": "https://github.com/callous-0923/agent-study"
    }
  ],
  "stages": [
    {
      "no": "第1层",
      "title": "Agent 理论基础",
      "time": "Ch0-3",
      "key": false,
      "desc": "建立直觉：Agent 是什么、和普通 LLM 差在哪、核心组件有哪些。",
      "items": [
        {
          "no": "Ch0",
          "title": "课程概览与环境搭建",
          "tech": "学习路线图 · 依赖安装 · API Key 配置",
          "path": "01-AI-Agent全栈课程/chapter_00_overview/00_course_overview.html",
          "py": "01-AI-Agent全栈课程/chapter_00_overview/00_course_overview.py"
        },
        {
          "no": "Ch1",
          "title": "第一个 Agent",
          "tech": "裸写 ReAct 循环 · Function Calling 原理",
          "path": "01-AI-Agent全栈课程/chapter_01_fundamentals/01_hello_agent.html",
          "py": "01-AI-Agent全栈课程/chapter_01_fundamentals/01_hello_agent.py"
        },
        {
          "no": "Ch2",
          "title": "Agent 核心组件",
          "tech": "规划器 · 记忆系统 · 工具设计黄金法则",
          "path": "01-AI-Agent全栈课程/chapter_02_components/02_agent_components.html",
          "py": "01-AI-Agent全栈课程/chapter_02_components/02_agent_components.py"
        },
        {
          "no": "Ch3",
          "title": "Agent 类型分类",
          "tech": "ReAct · Plan-Execute · Reflexion 对比",
          "path": "01-AI-Agent全栈课程/chapter_03_types/03_agent_types.html",
          "py": "01-AI-Agent全栈课程/chapter_03_types/03_agent_types.py"
        }
      ],
      "pass": "能说清 Agent 与普通 LLM 的本质区别；不看示例能手写一个最小 ReAct 循环。"
    },
    {
      "no": "第2层",
      "title": "工程实践与框架",
      "time": "Ch4-7",
      "key": false,
      "desc": "上手工程：主流框架、多智能体协作、怎么评测、面试怎么答。",
      "items": [
        {
          "no": "Ch4",
          "title": "主流框架实战",
          "tech": "LangChain Agent · LangGraph 状态机",
          "path": "01-AI-Agent全栈课程/chapter_04_frameworks/04_frameworks.html",
          "py": "01-AI-Agent全栈课程/chapter_04_frameworks/04_frameworks.py"
        },
        {
          "no": "Ch5",
          "title": "多智能体系统",
          "tech": "Writer+Reviewer 协作 · crewAI 风格",
          "path": "01-AI-Agent全栈课程/chapter_05_multi_agent/05_multi_agent.html",
          "py": "01-AI-Agent全栈课程/chapter_05_multi_agent/05_multi_agent.py"
        },
        {
          "no": "Ch6",
          "title": "评估与测试",
          "tech": "评测框架 · LLM-as-Judge · 生产 Checklist",
          "path": "01-AI-Agent全栈课程/chapter_06_evaluation/06_evaluation.html",
          "py": "01-AI-Agent全栈课程/chapter_06_evaluation/06_evaluation.py"
        },
        {
          "no": "Ch7",
          "title": "求职面试准备",
          "tech": "20 道高频面试题 · 项目指南 · 面试流程",
          "path": "01-AI-Agent全栈课程/chapter_07_interview/07_interview_prep.html",
          "py": "01-AI-Agent全栈课程/chapter_07_interview/07_interview_prep.py"
        }
      ],
      "pass": "能用 LangGraph 搭一个带状态流转的 Agent；能设计出 Writer + Reviewer 这类多智能体协作。"
    },
    {
      "no": "第3层",
      "title": "深度技术剖析",
      "time": "Ch8-12",
      "key": true,
      "badge": "核心分水岭",
      "desc": "啃源码级细节：Claude Code 架构、RAG 生产级方案、MCP / Tool Calling 协议底层。",
      "items": [
        {
          "no": "Ch8",
          "title": "Claude Code 架构",
          "tech": "nO 主循环 · h2A Steering · 上下文压缩 · SubAgent",
          "path": "01-AI-Agent全栈课程/chapter_08_claude_code/08_claude_code_architecture.html",
          "py": "01-AI-Agent全栈课程/chapter_08_claude_code/08_claude_code_architecture.py"
        },
        {
          "no": "Ch9",
          "title": "RAG 深度解析",
          "tech": "Chunk策略·Embedding选型·RRF·Cross-Encoder·生产失败模式",
          "path": "01-AI-Agent全栈课程/chapter_09_rag_deepdive/09_rag_deepdive.html",
          "py": "01-AI-Agent全栈课程/chapter_09_rag_deepdive/09_rag_deepdive.py"
        },
        {
          "no": "Ch10",
          "title": "MCP 协议详解",
          "tech": "2026-07-28 无状态核心 · 路由 · MRTR · 缓存",
          "path": "01-AI-Agent全栈课程/chapter_10_mcp/10_mcp_deepdive.html",
          "py": "01-AI-Agent全栈课程/chapter_10_mcp/10_mcp_deepdive.py"
        },
        {
          "no": "Ch11",
          "title": "Tool Calling 底层",
          "tech": "OpenAI/Anthropic · Tool Search/PTC · Strict",
          "path": "01-AI-Agent全栈课程/chapter_11_tool_calling/11_tool_calling_deepdive.html",
          "py": "01-AI-Agent全栈课程/chapter_11_tool_calling/11_tool_calling_deepdive.py"
        },
        {
          "no": "Ch12",
          "title": "Agent 生产基础设施",
          "tech": "OpenClaw 架构 · Harness · 生产化 Checklist",
          "path": "01-AI-Agent全栈课程/chapter_12_infrastructure/12_infrastructure.html",
          "py": "01-AI-Agent全栈课程/chapter_12_infrastructure/12_infrastructure.py"
        }
      ],
      "pass": "能讲清 Claude Code 主循环为什么这么设计；说得清 MCP 解决了什么协议层问题。"
    },
    {
      "no": "第4层",
      "title": "工程化与前沿",
      "time": "Ch13-18",
      "key": false,
      "desc": "补齐工程化：FastAPI 服务化、SQLite 持久化、A2A 协议、记忆系统、Computer Use、安全护栏。",
      "items": [
        {
          "no": "Ch13",
          "title": "FastAPI 服务化",
          "tech": "REST/SSE/WebSocket · 可运行 UI · Background/Webhook",
          "path": "01-AI-Agent全栈课程/chapter_13_fastapi/13_fastapi_agent_service.html",
          "py": "01-AI-Agent全栈课程/chapter_13_fastapi/13_fastapi_agent_service.py"
        },
        {
          "no": "Ch14",
          "title": "SQLite 持久化",
          "tech": "5 表 Schema · WAL 模式 · 审计查询",
          "path": "01-AI-Agent全栈课程/chapter_14_sqlite/14_sqlite_agent_storage.html",
          "py": "01-AI-Agent全栈课程/chapter_14_sqlite/14_sqlite_agent_storage.py"
        },
        {
          "no": "Ch15",
          "title": "Google A2A 协议",
          "tech": "AgentCard · Task · Artifact · Multi-Agent 协作",
          "path": "01-AI-Agent全栈课程/chapter_15_a2a/15_a2a_protocol.html",
          "py": "01-AI-Agent全栈课程/chapter_15_a2a/15_a2a_protocol.py"
        },
        {
          "no": "Ch16",
          "title": "MemGPT/Letta 记忆",
          "tech": "Core Memory · Heartbeat · Sleep-Time Compute",
          "path": "01-AI-Agent全栈课程/chapter_16_memgpt/16_memgpt_letta.html",
          "py": "01-AI-Agent全栈课程/chapter_16_memgpt/16_memgpt_letta.py"
        },
        {
          "no": "Ch17",
          "title": "Computer Use",
          "tech": "Screenshot-Action Loop · 坐标计算 · 安全沙箱",
          "path": "01-AI-Agent全栈课程/chapter_17_computer_use/17_computer_use.html",
          "py": "01-AI-Agent全栈课程/chapter_17_computer_use/17_computer_use.py"
        },
        {
          "no": "Ch18",
          "title": "Agent 安全与护栏",
          "tech": "Prompt Injection · 权限分级 · 4层防御",
          "path": "01-AI-Agent全栈课程/chapter_18_security/18_agent_security.html",
          "py": "01-AI-Agent全栈课程/chapter_18_security/18_agent_security.py"
        }
      ],
      "pass": "能把 Agent 包装成 FastAPI 服务，会话状态落到 SQLite，并加上基本的安全护栏。"
    },
    {
      "no": "第5层",
      "title": "高级架构与优化",
      "time": "Ch19-24",
      "key": false,
      "desc": "架构进阶：Agentic Workflow 模式、上下文工程、流式架构、DSPy 优化、代码 Agent 横评、可观测性。",
      "items": [
        {
          "no": "Ch19",
          "title": "Agentic Workflow 设计模式",
          "tech": "Reflection · Routing · Orchestrator-Worker 等 7 种",
          "path": "01-AI-Agent全栈课程/chapter_19_workflow_patterns/19_workflow_patterns.html",
          "py": "01-AI-Agent全栈课程/chapter_19_workflow_patterns/19_workflow_patterns.py"
        },
        {
          "no": "Ch20",
          "title": "Context Engineering",
          "tech": "Context Rot · 预算管理 · XML 结构化 Prompt",
          "path": "01-AI-Agent全栈课程/chapter_20_context_engineering/20_context_engineering.html",
          "py": "01-AI-Agent全栈课程/chapter_20_context_engineering/20_context_engineering.py"
        },
        {
          "no": "Ch21",
          "title": "Streaming & 实时架构",
          "tech": "EventBus · 断线恢复 · 人工审批 · Realtime",
          "path": "01-AI-Agent全栈课程/chapter_21_streaming/21_streaming_architecture.html",
          "py": "01-AI-Agent全栈课程/chapter_21_streaming/21_streaming_architecture.py"
        },
        {
          "no": "Ch22",
          "title": "DSPy 自动优化",
          "tech": "Signature→Module→Optimizer · 与 LangChain 互补",
          "path": "01-AI-Agent全栈课程/chapter_22_dspy/22_dspy.html",
          "py": "01-AI-Agent全栈课程/chapter_22_dspy/22_dspy.py"
        },
        {
          "no": "Ch23",
          "title": "代码 Agent 架构横评",
          "tech": "CodeAct · ACI · Plan-Execute · SWE-bench",
          "path": "01-AI-Agent全栈课程/chapter_23_code_agents/23_code_agents.html",
          "py": "01-AI-Agent全栈课程/chapter_23_code_agents/23_code_agents.py"
        },
        {
          "no": "Ch24",
          "title": "Agent 可观测性",
          "tech": "Tracing Span 树 · LangSmith vs LangFuse",
          "path": "01-AI-Agent全栈课程/chapter_24_observability/24_observability.html",
          "py": "01-AI-Agent全栈课程/chapter_24_observability/24_observability.py"
        }
      ],
      "pass": "能独立设计一条 Agentic Workflow；会做上下文压缩、流式输出与基础可观测埋点。"
    },
    {
      "no": "第6层",
      "title": "基础能力补强",
      "time": "Ch25-28",
      "key": false,
      "desc": "补基础短板：向量库选型、模型路由、Prompt 工程、语义缓存。",
      "items": [
        {
          "no": "Ch25",
          "title": "向量数据库选型",
          "tech": "Chroma · Pinecone · Milvus · Qdrant",
          "path": "01-AI-Agent全栈课程/chapter_25_vectordb/25_vectordb.html",
          "py": "01-AI-Agent全栈课程/chapter_25_vectordb/25_vectordb.py"
        },
        {
          "no": "Ch26",
          "title": "模型路由策略",
          "tech": "Threshold · Cascade · Semantic · Cost-Aware",
          "path": "01-AI-Agent全栈课程/chapter_26_model_routing/26_model_routing.html",
          "py": "01-AI-Agent全栈课程/chapter_26_model_routing/26_model_routing.py"
        },
        {
          "no": "Ch27",
          "title": "Agent Prompt 工程",
          "tech": "System Prompt 6 模块模板 · 工具描述评分卡",
          "path": "01-AI-Agent全栈课程/chapter_27_prompt_eng/27_prompt_engineering.html",
          "py": "01-AI-Agent全栈课程/chapter_27_prompt_eng/27_prompt_engineering.py"
        },
        {
          "no": "Ch28",
          "title": "语义缓存与 Token 优化",
          "tech": "三级缓存 · Token 预算管理",
          "path": "01-AI-Agent全栈课程/chapter_28_cache/28_cache.html",
          "py": "01-AI-Agent全栈课程/chapter_28_cache/28_cache.py"
        }
      ],
      "pass": "能根据场景选向量库；会按成本/质量做模型路由；能上语义缓存把 token 成本压下来。"
    },
    {
      "no": "第7层",
      "title": "专家级进阶",
      "time": "Ch29-36",
      "key": false,
      "desc": "专家级话题：多模态、可靠性工程、评测基准、自改进、Prompt Cache、微调、数据飞轮、纵深安全。",
      "items": [
        {
          "no": "Ch29",
          "title": "Multi-Modal Agent",
          "tech": "视觉+文本联合推理 · Token 预算",
          "path": "01-AI-Agent全栈课程/chapter_29_multimodal/29_multimodal.html",
          "py": "01-AI-Agent全栈课程/chapter_29_multimodal/29_multimodal.py"
        },
        {
          "no": "Ch30",
          "title": "Agent 可靠性工程",
          "tech": "熔断器 · 退避重试 · 幂等 · 降级",
          "path": "01-AI-Agent全栈课程/chapter_30_reliability/30_reliability.html",
          "py": "01-AI-Agent全栈课程/chapter_30_reliability/30_reliability.py"
        },
        {
          "no": "Ch31",
          "title": "Agent 评测体系深度",
          "tech": "GAIA · AgentBench · WebArena · ClawBench · tau-bench · SWE-bench",
          "path": "01-AI-Agent全栈课程/chapter_31_benchmarks/31_benchmarks.html",
          "py": "01-AI-Agent全栈课程/chapter_31_benchmarks/31_benchmarks.py"
        },
        {
          "no": "Ch32",
          "title": "Self-Improving Agent",
          "tech": "Bad Case 收集→自动改 Prompt→评测验证",
          "path": "01-AI-Agent全栈课程/chapter_32_self_improving/32_self_improving.html",
          "py": "01-AI-Agent全栈课程/chapter_32_self_improving/32_self_improving.py"
        },
        {
          "no": "Ch33",
          "title": "Prompt Caching & 推理优化",
          "tech": "Anthropic Cache · KV共享 · 推测解码",
          "path": "01-AI-Agent全栈课程/chapter_33_prompt_cache/33_prompt_cache.html",
          "py": "01-AI-Agent全栈课程/chapter_33_prompt_cache/33_prompt_cache.py"
        },
        {
          "no": "Ch34",
          "title": "模型微调 for Function Calling",
          "tech": "LoRA · 微调数据准备 · 成本收益",
          "path": "01-AI-Agent全栈课程/chapter_34_finetune/34_finetune.html",
          "py": "01-AI-Agent全栈课程/chapter_34_finetune/34_finetune.py"
        },
        {
          "no": "Ch35",
          "title": "数据飞轮",
          "tech": "交互采集→Bad Case识别→自动触发改进",
          "path": "01-AI-Agent全栈课程/chapter_35_data_flywheel/35_data_flywheel.html",
          "py": "01-AI-Agent全栈课程/chapter_35_data_flywheel/35_data_flywheel.py"
        },
        {
          "no": "Ch36",
          "title": "Agent 纵深安全",
          "tech": "Canary Token · 分层隔离 · 行为沙箱",
          "path": "01-AI-Agent全栈课程/chapter_36_defense/36_defense.html",
          "py": "01-AI-Agent全栈课程/chapter_36_defense/36_defense.py"
        }
      ],
      "pass": "能设计 Agent 的可靠性与纵深安全方案；看得懂主流评测基准，知道各自测的是什么。"
    }
  ],
  "extra": null,
  "agentPath": null,
  "env": {
    "title": "运行环境",
    "sub": "课程自带 requirements.txt。Ch8 之后大多只用标准库，不装依赖也能读代码。",
    "code": "cd C:\\StudyAI\\01-AI-Agent全栈课程\n\n# 1) 安装课程依赖（Ch1-5 需要 openai / langchain / langgraph）\npython -m pip install -r requirements.txt\n\n# 2) 配置 API Key —— 在课程根目录新建 .env\n#    OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx\n#    OPENAI_BASE_URL=https://api.deepseek.com/v1   # 或用国产模型\n#    LLM_MODEL=deepseek-chat\n\n# 3) 国内 pip 加速（可选）\npip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple\n\n# 4) 验证 Python 版本（课程要求 3.10+）\npython --version",
    "note": "课程 <code>Ch0</code> 里有完整的 API Key 配置指南与一键环境检查脚本。国产模型（DeepSeek / 通义千问）改 <code>OPENAI_BASE_URL</code> 即可直接跑。"
  },
  "paths": {
    "title": "按目标选路径",
    "sub": "来自课程 Ch0 的学习建议",
    "items": [
      {
        "t": "新手入门",
        "d": "按 Ch0 → Ch36 顺序，每章 1–2 小时",
        "chapters": "全部 37 章"
      },
      {
        "t": "有基础",
        "d": "直接跳 Ch8 开始深度技术",
        "chapters": "Ch8–36"
      },
      {
        "t": "面试突击",
        "d": "高频考点 8 章",
        "chapters": "Ch7 · Ch8 · Ch9 · Ch10 · Ch11 · Ch15 · Ch18 · Ch19"
      },
      {
        "t": "构建产品",
        "d": "服务化 + 持久化 + 可观测 + 路由 + 缓存",
        "chapters": "Ch13 · Ch14 · Ch24 · Ch26 · Ch28"
      },
      {
        "t": "降本增效",
        "d": "路由与缓存组合拳",
        "chapters": "Ch26 · Ch28 · Ch33"
      }
    ]
  },
  "onlineBooks": [
    {
      "t": "课程原仓库（GitHub）",
      "u": "https://github.com/callous-0923/agent-study"
    },
    {
      "t": "课程在线版（作者站点）",
      "u": "https://callous-0923.github.io/agent-study/index.html"
    }
  ]
};
