#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 陪读：服务商预设、密钥存取、系统提示词、演示模式、模型调用、错误翻译。

从 server.py 抽出来的独立模块 —— 不依赖 HTTP 层，可以单独测试。
"""

import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

WEBAPP = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------
# AI 陪读配置
# ---------------------------------------------------------------------
# 密钥只存在本机这个文件里，不进版本控制，也从不回传给浏览器（只返回掩码）。
AI_CONFIG_FILE = WEBAPP / "data" / "ai-config.json"

# 预设服务商（全部走 OpenAI 兼容协议）
AI_PRESETS = {
    "deepseek": {
        "name": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat",
        "tag": "推荐", "badge": "cheap",
        "desc": "国内直连、价格极低，最省事的选择",
        "home": "https://platform.deepseek.com/api_keys",
        "key_hint": "sk- 开头",
    },
    "qwen": {
        "name": "通义千问", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus",
        "tag": "有免费额度", "badge": "free",
        "desc": "阿里云百炼，新用户通常有免费 token",
        "home": "https://bailian.console.aliyun.com/",
        "key_hint": "sk- 开头",
    },
    "moonshot": {
        "name": "Kimi", "base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k",
        "tag": "长文本", "badge": "cheap",
        "desc": "月之暗面，适合读长章节",
        "home": "https://platform.moonshot.cn/console/api-keys",
        "key_hint": "sk- 开头",
    },
    "openai": {
        "name": "OpenAI", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini",
        "tag": "需代理", "badge": "paid",
        "desc": "国内直连通常不通，需要网络代理",
        "home": "https://platform.openai.com/api-keys",
        "key_hint": "sk- 开头",
    },
    "ollama": {
        "name": "Ollama 本地", "base_url": "http://127.0.0.1:11434/v1", "model": "qwen2.5:7b",
        "tag": "完全免费", "badge": "free",
        "desc": "跑在自己电脑上，断网可用；需先装 Ollama 并 pull 模型",
        "home": "https://ollama.com/download",
        "key_hint": "本地服务不用填 Key",
    },
    "mock": {
        "name": "演示模式", "base_url": "mock://demo", "model": "mock-fish",
        "tag": "不联网", "badge": "demo",
        "desc": "返回固定示例，只用来看界面长什么样",
        "home": "",
        "key_hint": "不需要 Key",
    },
}

AI_CONFIG_DEFAULT = {
    "preset": "deepseek",
    "base_url": AI_PRESETS["deepseek"]["base_url"],
    "model": AI_PRESETS["deepseek"]["model"],
    "api_key": "",
    "temperature": 0.7,
    "max_tokens": 1600,
}

_ai_lock = threading.Lock()


def load_ai_config():
    """读取 AI 配置；文件不存在则返回默认值。"""
    cfg = dict(AI_CONFIG_DEFAULT)
    try:
        if AI_CONFIG_FILE.is_file():
            with open(AI_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                cfg.update({k: v for k, v in saved.items() if k in AI_CONFIG_DEFAULT})
    except Exception:
        pass
    return cfg


def save_ai_config(cfg):
    """原子写入配置，并尽量收紧文件权限。"""
    AI_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = AI_CONFIG_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, AI_CONFIG_FILE)
    try:
        os.chmod(AI_CONFIG_FILE, 0o600)
    except Exception:
        pass


def mask_key(key):
    """密钥只回显卡号，绝不回显完整内容。"""
    if not key:
        return ""
    key = str(key)
    if len(key) <= 10:
        return "****"
    return key[:6] + "…" + key[-4:]


def build_system_prompt(ctx):
    """把「你正在读什么」编织进系统提示词 —— 这是陪读和普通聊天机器人的区别。"""
    ctx = ctx or {}
    lines = [
        "你是「大肥鱼」，一只陪学生读书的助教鱼。你的学生正在读《AI Agent 全栈课程》。",
        "",
        "【当前阅读上下文】",
    ]
    if ctx.get("chapter"):
        lines.append("· 章节：" + str(ctx["chapter"]))
    if ctx.get("path"):
        lines.append("· 文件：" + str(ctx["path"]))
    if ctx.get("heading"):
        lines.append("· 所在小节：" + str(ctx["heading"]))
    if ctx.get("progress"):
        lines.append("· 阅读进度：" + str(ctx["progress"]))

    sel = (ctx.get("selection") or "").strip()
    if sel:
        lines += ["", "【学生刚选中的原文】", sel[:3000]]

    excerpt = (ctx.get("excerpt") or "").strip()
    if excerpt:
        lines += ["", "【本章正文节选】", excerpt[:9000]]

    lines += [
        "",
        "【陪读原则】",
        "1. 回答要紧贴当前章节的内容，不要泛泛而谈。",
        "2. 讲抽象概念一定配具体例子；能用代码说明就用代码。",
        "3. 学生问「为什么」时，先给结论，再讲原因。",
        "4. 不确定的地方直说不知道，绝不编造 API、论文或数据。",
        "5. 回答简洁，多用小标题、列表、代码块，不要复述学生的问题。",
        "6. 超出本章范围的问题，简要回答并指出哪一章会深入。",
        "7. 中文回答。语气像个耐心的师兄，不要油腻，少用表情符号。",
    ]
    return "\n".join(lines)


def mock_stream_reply(messages, ctx):
    """演示模式：不联网，返回固定样例，用来验证界面与流式链路是否打通。"""
    last = ""
    for m in reversed(messages or []):
        if m.get("role") == "user":
            last = (m.get("content") or "").strip()
            break
    sel = (ctx.get("selection") or "").strip()
    chap = (ctx.get("chapter") or "当前章节")

    if sel:
        return (
            "**（演示模式，未连接真实模型）**\n\n"
            "你选中的这段是：\n\n> " + sel[:200].replace("\n", "\n> ") + "\n\n"
            "**这段话在讲什么** —— 它属于《" + chap + "》的核心论证部分。\n\n"
            "**为什么重要** —— 它把抽象的设计原则落到了可执行的动作上。\n\n"
            "**举个例子** —— 假设你要让 Agent 完成「查天气」：\n\n"
            "```python\n"
            "tools = [{\"name\": \"get_weather\", \"description\": \"查询指定城市的实时天气\"}]\n"
            "```\n\n"
            "配置真实模型后，这里会变成针对你选中内容的、贴合上下文的讲解。"
        )
    if last:
        return (
            "**（演示模式，未连接真实模型）**\n\n"
            "你问的是：「" + last[:80] + "」\n\n"
            "**先给结论** —— 这是个好问题，它正好卡在《" + chap + "》的关键处。\n\n"
            "**为什么** —— Agent 的能力边界，本质上由「能调用什么工具」和「如何决定调用哪个工具」共同决定。\n\n"
            "**一个例子**\n\n"
            "| 层 | 做什么 | 出错的后果 |\n"
            "|---|---|---|\n"
            "| 规划 | 拆解任务 | 走错方向 |\n"
            "| 工具 | 真正执行 | 拿到错误数据 |\n"
            "| 观察 | 校验结果 | 带着错误往上走 |\n\n"
            "点右上角 ⚙ 配置一个模型，我就能真正读着你这一章回答问题。"
        )
    return (
        "**（演示模式，未连接真实模型）**\n\n"
        "我是大肥鱼，负责陪你读这本书。现在可以：\n\n"
        "- 在讲义里**选中一段文字**，旁边会冒出「问大肥鱼」\n"
        "- 点下面的快捷指令，让我总结章节或出题考你\n"
        "- 直接在输入框里问任何问题\n\n"
        "> 演示模式只能返回固定样例。配置真实模型后，我才能读着你当前这一章回答。"
    )


def classify_error(e):
    """把模型调用失败翻译成人话。

    返回 dict: {kind, message, hint}
      kind    —— 前端用来决定怎么展示（auth / network / billing ...）
      message —— 发生了什么
      hint    —— 该怎么办
    """
    import socket
    import urllib.error

    code = None
    detail = ""
    if isinstance(e, urllib.error.HTTPError):
        code = e.code
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:
            detail = ""
        if not detail:
            detail = str(e)
    else:
        detail = str(e) or e.__class__.__name__

    low = detail.lower()

    if code == 401 or "invalid_api_key" in low or "incorrect api key" in low \
            or "unauthorized" in low or "invalid token" in low:
        return {"kind": "auth",
                "message": "API Key 无效或已过期",
                "hint": "确认 Key 复制完整（首尾不要有空格），或去服务商后台重新生成一个"}

    if code == 403:
        return {"kind": "forbidden",
                "message": "这个 Key 没有调用权限",
                "hint": "确认账号已开通对应模型；部分服务商要求先实名或充值才能调用"}

    if code == 404:
        return {"kind": "notfound",
                "message": "接口地址或模型名不存在",
                "hint": "接口地址一般以 /v1 结尾；模型名要和服务商文档完全一致（如 deepseek-chat）"}

    if code == 402 or "insufficient" in low or "balance" in low \
            or "quota" in low or "欠费" in detail or "额度" in detail:
        return {"kind": "billing",
                "message": "账户余额不足或额度已用完",
                "hint": "去服务商后台充值后再试"}

    if code == 429:
        return {"kind": "ratelimit",
                "message": "请求太频繁，被限流了",
                "hint": "等几十秒再试；免费额度通常有每分钟次数限制"}

    if code and 500 <= code < 600:
        return {"kind": "server",
                "message": "服务商那边出错了（HTTP %d）" % code,
                "hint": "稍后重试；持续失败可以换一家服务商"}

    if isinstance(e, (TimeoutError, socket.timeout)) or "timed out" in low:
        return {"kind": "timeout",
                "message": "连接超时",
                "hint": "检查网络；国内直连 OpenAI 通常需要代理"}

    if "getaddrinfo" in low or "name or service not known" in low \
            or "connection refused" in low or "connection reset" in low \
            or "failed to establish" in low:
        return {"kind": "network",
                "message": "连不上这个接口地址",
                "hint": "检查地址拼写；用本地 Ollama 的话要先启动服务（默认 127.0.0.1:11434）"}

    if "certificate" in low or "ssl" in low:
        return {"kind": "ssl",
                "message": "TLS 证书校验失败",
                "hint": "公共 API 一般不会这样；自建服务用自签证书需要额外配置"}

    return {"kind": "unknown",
            "message": (detail.strip() or str(e))[:300],
            "hint": "把这个错误发给开发者看看"}


def llm_call(cfg, messages, stream=False, max_tokens=None):
    """调用 OpenAI 兼容接口。stream=True 时返回响应对象供逐行读取。"""
    import urllib.request
    base = str(cfg.get("base_url") or "").rstrip("/")
    url = base + "/chat/completions"
    payload = {
        "model": cfg.get("model") or "gpt-4o-mini",
        "messages": messages,
        "temperature": float(cfg.get("temperature") or 0.7),
        "max_tokens": int(max_tokens or cfg.get("max_tokens") or 1600),
        "stream": bool(stream),
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + str(cfg.get("api_key") or ""),
        "User-Agent": "agent-study-platform/1.0",
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=headers, method="POST")
    resp = urllib.request.urlopen(req, timeout=120)
    if stream:
        return resp
    with resp:
        obj = json.loads(resp.read().decode("utf-8", "replace"))
    try:
        return obj["choices"][0]["message"]["content"]
    except Exception:
        return json.dumps(obj, ensure_ascii=False)[:500]


# 供 server.py 复用同一把锁
LOCK = _ai_lock
