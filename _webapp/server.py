#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent学习平台 · 本地学习服务器
=====================================================================
- 仅监听 127.0.0.1，不对外网开放
- 所有路径经 realpath 解析后必须落在 ROOT 之内（防目录穿越）
- 提供：静态资源 / 目录树 / 文件内容 / 原始字节 / 全文搜索 / 统计
- 仅用 Python 标准库，无需 pip install
"""
import os
import sys
import io
import re
import json
import gzip
import time
import socket
import mimetypes
import threading
import webbrowser
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ---------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------
ROOT     = Path(r"C:\StudyAI").resolve()
WEBAPP   = Path(__file__).resolve().parent
STATIC   = WEBAPP / "static"

HOST     = "127.0.0.1"
PORT     = 8777

MAX_TEXT      = 8  * 1024 * 1024      # 文本类文件读取上限 8 MB
MAX_RAW       = 64 * 1024 * 1024      # 原始字节流上限 64 MB
SEARCH_LIMIT  = 200                   # 搜索最大结果数
SEARCH_MAXSIZE= 2  * 1024 * 1024      # 单文件搜索上限

# ---------------------------------------------------------------------
# AI 陪读配置
# ---------------------------------------------------------------------
# 密钥只存在本机这个文件里，不进版本控制，也从不回传给浏览器（只返回掩码）。
AI_CONFIG_FILE = WEBAPP / ".ai-config.json"

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


def _chunked_write(handler, text):
    """SSE 分块写入。客户端断开时静默返回 False。"""
    data = text.encode("utf-8")
    if not data:
        return True
    try:
        handler.wfile.write(b"%x\r\n" % len(data))
        handler.wfile.write(data)
        handler.wfile.write(b"\r\n")
        handler.wfile.flush()
        return True
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False


def _chunked_end(handler):
    try:
        handler.wfile.write(b"0\r\n\r\n")
        handler.wfile.flush()
    except Exception:
        pass


def sse_event(handler, obj):
    """发送一条 SSE 事件。"""
    return _chunked_write(handler, "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n")


# 这些目录不出现在树里
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".ipynb_checkpoints",
    ".github", ".vscode", ".idea", "_webapp", "_zips", "_scripts",
    "_IDM导入清单", ".pytest_cache", "dist", "build", ".mypy_cache",
}

# 已知无法在浏览器里看的东西
BINARY_EXT = {
    ".graffle", ".npy", ".npz", ".sqlite3", ".sqlite", ".db", ".m4a", ".mp3",
    ".mp4", ".avi", ".mov", ".wav", ".pptx", ".ppt", ".docx", ".doc", ".xlsx",
    ".xls", ".pkl", ".pickle", ".bin", ".gguf", ".safetensors", ".pt", ".pth",
    ".onnx", ".zip", ".tar", ".gz", ".7z", ".rar", ".exe", ".dll", ".so",
    ".DS_Store", ".woff", ".woff2", ".ttf", ".otf", ".eot",
}

KIND_MAP = {
    ".md": "markdown", ".markdown": "markdown", ".mdx": "markdown",
    ".ipynb": "notebook",
    ".pdf": "pdf",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image",
    ".svg": "image", ".webp": "image", ".bmp": "image", ".ico": "image",
    ".html": "html", ".htm": "html",
    ".py": "code", ".js": "code", ".mjs": "code", ".cjs": "code",
    ".ts": "code", ".tsx": "code", ".jsx": "code",
    ".java": "code", ".c": "code", ".h": "code", ".cpp": "code", ".hpp": "code",
    ".cs": "code", ".go": "code", ".rs": "code", ".rb": "code", ".php": "code",
    ".swift": "code", ".kt": "code", ".scala": "code", ".r": "code",
    ".sh": "code", ".bash": "code", ".zsh": "code", ".ps1": "code", ".bat": "code",
    ".yaml": "code", ".yml": "code", ".json": "code", ".xml": "code",
    ".toml": "code", ".ini": "code", ".cfg": "code", ".conf": "code",
    ".css": "code", ".scss": "code", ".less": "code", ".sql": "code",
    ".dockerfile": "code", ".makefile": "code", ".cmake": "code",
    ".txt": "text", ".log": "text", ".csv": "text", ".tsv": "text",
    ".example": "text", ".env": "text", ".gitignore": "text",
    ".gitattributes": "text", ".editorconfig": "text", ".dockerignore": "text",
}

LANG_MAP = {
    ".py": "python", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".jsx": "javascript",
    ".java": "java", ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp",
    ".cs": "csharp", ".go": "go", ".rs": "rust", ".rb": "ruby", ".php": "php",
    ".swift": "swift", ".kt": "kotlin", ".scala": "scala", ".r": "r",
    ".sh": "bash", ".bash": "bash", ".zsh": "bash", ".ps1": "powershell",
    ".bat": "dos", ".yaml": "yaml", ".yml": "yaml", ".json": "json",
    ".xml": "xml", ".toml": "ini", ".ini": "ini", ".cfg": "ini",
    ".css": "css", ".scss": "scss", ".less": "less", ".sql": "sql",
    ".html": "html", ".htm": "html", ".md": "markdown", ".markdown": "markdown",
    ".dockerfile": "dockerfile", ".cmake": "cmake", ".txt": "plaintext",
}


def get_ext(name: str) -> str:
    """取扩展名；'.gitignore' 这类整体作为扩展名"""
    n = name.lower()
    if n.startswith(".") and n.count(".") == 1:
        return n
    if n in ("dockerfile", "makefile", "cmakelists.txt"):
        return "." + n
    return os.path.splitext(n)[1]


def classify(name: str, size: int):
    """返回 (kind, language, renderable)"""
    ext = get_ext(name)
    if ext in BINARY_EXT:
        return "binary", None, False
    kind = KIND_MAP.get(ext)
    if kind is None:
        kind = "binary" if size > MAX_RAW else "unknown"
    lang = LANG_MAP.get(ext)
    renderable = kind in ("markdown", "notebook", "pdf", "image", "html",
                          "code", "text") and size <= MAX_RAW
    if kind in ("code", "text", "markdown", "notebook") and size > MAX_TEXT:
        renderable = False
    return kind, lang, renderable


# ---------------------------------------------------------------------
# 路径安全
# ---------------------------------------------------------------------
class UnsafePath(Exception):
    pass


def safe_path(rel: str) -> Path:
    """把请求的相对路径解析为 ROOT 内的绝对路径，越界即抛异常"""
    if rel is None:
        rel = ""
    rel = urllib.parse.unquote(rel).replace("\\", "/").strip("/")
    if "\x00" in rel:
        raise UnsafePath("NUL in path")
    p = (ROOT / rel).resolve()
    try:
        p.relative_to(ROOT)
    except ValueError:
        raise UnsafePath(f"outside root: {rel}")
    return p


def rel_of(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace("\\", "/")


# ---------------------------------------------------------------------
# 目录树
# ---------------------------------------------------------------------
def list_dir(p: Path):
    dirs, files = [], []
    try:
        entries = list(os.scandir(p))
    except (PermissionError, FileNotFoundError, NotADirectoryError) as e:
        return dirs, files

    for e in entries:
        name = e.name
        if name.startswith(".") and name not in (".gitignore", ".gitattributes",
                                                  ".editorconfig", ".dockerignore",
                                                  ".env", ".example"):
            continue
        try:
            if e.is_dir(follow_symlinks=False):
                if name in SKIP_DIRS:
                    continue
                try:
                    has_kids = any(True for _ in os.scandir(e.path))
                except OSError:
                    has_kids = False
                dirs.append({
                    "name": name,
                    "path": rel_of(Path(e.path)),
                    "type": "dir",
                    "hasChildren": has_kids,
                })
            elif e.is_file(follow_symlinks=False):
                st = e.stat()
                kind, lang, renderable = classify(name, st.st_size)
                files.append({
                    "name": name,
                    "path": rel_of(Path(e.path)),
                    "type": "file",
                    "size": st.st_size,
                    "mtime": int(st.st_mtime),
                    "ext": get_ext(name),
                    "kind": kind,
                    "language": lang,
                    "renderable": renderable,
                })
        except OSError:
            continue

    dirs.sort(key=lambda x: x["name"].lower())
    files.sort(key=lambda x: (x["kind"] == "binary", x["name"].lower()))
    return dirs, files


# ---------------------------------------------------------------------
# 搜索
# ---------------------------------------------------------------------
_search_cache = {"ts": 0, "index": []}
_stats_cache  = {"ts": 0, "data": None}

SEARCHABLE = {"markdown", "notebook", "code", "text"}


def build_index():
    now = time.time()
    if now - _search_cache["ts"] < 300 and _search_cache["index"]:
        return _search_cache["index"]
    idx = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            fp = Path(dirpath) / fn
            try:
                st = fp.stat()
            except OSError:
                continue
            if st.st_size > SEARCH_MAXSIZE:
                continue
            kind, lang, renderable = classify(fn, st.st_size)
            if kind in SEARCHABLE and renderable:
                idx.append((rel_of(fp), fn, fp, kind))
    _search_cache["ts"] = now
    _search_cache["index"] = idx
    return idx


def do_search(query: str, limit: int):
    t0 = time.time()
    q = query.lower()
    results = []
    total_hits = 0
    for rel, name, fp, kind in build_index():
        if len(results) >= limit:
            break
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        low = text.lower()
        pos = low.find(q)
        if pos < 0:
            continue
        lines = text.splitlines()
        hits = []
        # 定位命中行
        line_no = low[:pos].count("\n")
        start = max(0, line_no - 1)
        end = min(len(lines), line_no + 3)
        for i in range(start, end):
            raw = lines[i]
            hits.append({
                "line": i + 1,
                "text": raw[:300],
                "match": q in raw.lower(),
            })
        cnt = low.count(q)
        total_hits += cnt
        results.append({
            "path": rel, "name": name, "kind": kind,
            "hits": hits, "count": cnt,
        })
    return {
        "query": query,
        "count": len(results),
        "totalHits": total_hits,
        "elapsed": round(time.time() - t0, 2),
        "results": results,
    }


# ---------------------------------------------------------------------
# HTTP 处理
# ---------------------------------------------------------------------
CT_JSON = "application/json; charset=utf-8"


class Handler(BaseHTTPRequestHandler):
    server_version = "agent-study-platform/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # 静音常规请求，只留错误
        if args and str(args[0]).startswith(("4", "5")):
            sys.stderr.write("  [%s] %s\n" % (self.log_date_time_string(), fmt % args))

    # ---------- 工具 ----------
    def _send(self, code, body: bytes, ctype: str, extra=None, gzip_ok=True):
        headers = {"Content-Type": ctype, "Cache-Control": "no-cache"}
        if extra:
            headers.update(extra)
        if (gzip_ok and isinstance(body, bytes) and len(body) > 2048
                and "gzip" in self.headers.get("Accept-Encoding", "")):
            body = gzip.compress(body, 6)
            headers["Content-Encoding"] = "gzip"
        headers["Content-Length"] = str(len(body))
        self.send_response(code)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj, code=200):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, raw, CT_JSON)

    def _err(self, code, msg):
        self._json({"error": msg, "code": code}, code)

    def _q(self, key, default=""):
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        return params.get(key, [default])[0]

    # ---------- 路由 ----------
    def do_GET(self):
        try:
            return self._route()
        except UnsafePath as e:
            return self._err(403, "路径越界: %s" % e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._err(500, "%s: %s" % (type(e).__name__, e))

    def do_HEAD(self):
        return self.do_GET()

    def _route(self):
        path = urllib.parse.urlparse(self.path).path

        if path in ("/", "/index.html"):
            return self._static("index.html")

        # 部分浏览器无视 <link rel="icon"> 仍直接请求根路径
        if path == "/favicon.ico":
            return self._static("favicon.ico")
        if path == "/apple-touch-icon.png":
            return self._static("apple-touch-icon.png")

        if path.startswith("/static/"):
            return self._static(path[len("/static/"):])

        # /files/<相对路径> —— 按真实目录结构提供文件，
        # 让本地 HTML 多页站点（相对链接导航）能在 iframe 里正常工作。
        # 对比 /api/raw?path=... ：后者会因浏览器解析相对URL时丢弃 query 而失效。
        if path.startswith("/files/"):
            return self._serve_file(urllib.parse.unquote(path[len("/files/"):]))

        if path == "/api/stats":
            return self._api_stats()
        if path == "/api/tree":
            return self._api_tree()
        if path == "/api/file":
            return self._api_file()
        if path == "/api/raw":
            return self._api_raw()
        if path == "/api/search":
            return self._api_search()
        if path == "/api/ping":
            return self._json({"ok": True, "root": str(ROOT)})

        # ---- AI 陪读 ----
        if path == "/api/ai/config":
            return self._api_ai_config_get()
        if path == "/api/ai/presets":
            return self._json({"presets": AI_PRESETS})

        return self._err(404, "未知路径: %s" % path)

    # ---------- POST ----------
    def do_POST(self):
        try:
            return self._route_post()
        except UnsafePath as e:
            return self._err(403, "路径越界: %s" % e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                return self._err(500, "%s: %s" % (type(e).__name__, e))
            except Exception:
                pass

    def _route_post(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/ai/config":
            return self._api_ai_config_set()
        if path == "/api/ai/chat":
            return self._api_ai_chat()
        if path == "/api/ai/test":
            return self._api_ai_test()
        return self._err(404, "未知路径: %s" % path)

    def _read_body(self, limit=256 * 1024):
        """读取 POST body，带长度上限。"""
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0:
            return b""
        n = min(n, limit)
        return self.rfile.read(n)

    # ---------- AI 陪读实现 ----------
    def _api_ai_config_get(self):
        cfg = load_ai_config()
        return self._json({
            "configured": bool(cfg.get("api_key")) or cfg.get("base_url", "").startswith("mock://"),
            "preset": cfg.get("preset"),
            "base_url": cfg.get("base_url"),
            "model": cfg.get("model"),
            "key_masked": mask_key(cfg.get("api_key")),
            "temperature": cfg.get("temperature"),
            "max_tokens": cfg.get("max_tokens"),
        })

    def _api_ai_config_set(self):
        raw = self._read_body()
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return self._err(400, "请求体不是合法 JSON")

        with _ai_lock:
            cfg = load_ai_config()

            preset = str(data.get("preset") or cfg.get("preset") or "").strip()
            if preset and preset in AI_PRESETS:
                cfg["preset"] = preset
                # 选了预设且没显式改地址时，跟随预设
                if not data.get("base_url"):
                    cfg["base_url"] = AI_PRESETS[preset]["base_url"]
                if not data.get("model"):
                    cfg["model"] = AI_PRESETS[preset]["model"]

            for k in ("base_url", "model"):
                if data.get(k):
                    cfg[k] = str(data[k]).strip()

            # 密钥：传空字符串表示"清除"，不传表示"保持不变"
            if "api_key" in data:
                cfg["api_key"] = str(data.get("api_key") or "").strip()

            for k, lo, hi in (("temperature", 0.0, 2.0), ("max_tokens", 128, 8192)):
                if k in data and data[k] is not None:
                    try:
                        cfg[k] = max(lo, min(hi, float(data[k]) if k == "temperature" else int(data[k])))
                    except (TypeError, ValueError):
                        pass

            save_ai_config(cfg)

        return self._json({
            "ok": True,
            "configured": bool(cfg.get("api_key")) or str(cfg.get("base_url", "")).startswith("mock://"),
            "preset": cfg.get("preset"),
            "base_url": cfg.get("base_url"),
            "model": cfg.get("model"),
            "key_masked": mask_key(cfg.get("api_key")),
            "temperature": cfg.get("temperature"),
            "max_tokens": cfg.get("max_tokens"),
        })

    @staticmethod
    def _classify_llm_error(e):
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

    def _api_ai_test(self):
        """测试连通性：发一个极短的请求，返回耗时与模型回复。"""
        raw = self._read_body()
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            data = {}
        cfg = load_ai_config()
        if data.get("base_url"):
            cfg["base_url"] = str(data["base_url"]).strip()
        if data.get("model"):
            cfg["model"] = str(data["model"]).strip()
        if data.get("api_key"):
            cfg["api_key"] = str(data["api_key"]).strip()

        if not cfg.get("base_url"):
            return self._json({"ok": False, "kind": "empty",
                               "error": "还没填接口地址",
                               "hint": "选一个服务商就会自动填好"}, 200)

        if str(cfg["base_url"]).startswith("mock://"):
            return self._json({"ok": True, "ms": 12, "reply": "演示模式无需联网",
                               "model": cfg.get("model")})

        if not cfg.get("api_key"):
            return self._json({"ok": False, "kind": "nokey",
                               "error": "还没填 API Key",
                               "hint": "去服务商后台创建一个，粘贴到上面的输入框"}, 200)

        t0 = time.time()
        try:
            reply = self._llm_call(cfg, [{"role": "user", "content": "只回复两个字：你好"}],
                                   stream=False, max_tokens=16)
        except Exception as e:
            info = self._classify_llm_error(e)
            info.update({"ok": False, "error": info.pop("message")})
            return self._json(info, 200)
        return self._json({
            "ok": True,
            "ms": int((time.time() - t0) * 1000),
            "reply": (reply or "")[:60],
            "model": cfg.get("model"),
        })

    def _llm_call(self, cfg, messages, stream=False, max_tokens=None):
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

    def _api_ai_chat(self):
        raw = self._read_body(limit=512 * 1024)
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return self._err(400, "请求体不是合法 JSON")

        cfg = load_ai_config()
        ctx = data.get("context") or {}
        messages = data.get("messages") or []
        if not isinstance(messages, list) or not messages:
            return self._err(400, "messages 不能为空")

        is_mock = str(cfg.get("base_url") or "").startswith("mock://")
        if not is_mock and not cfg.get("api_key"):
            return self._err(400, "还没配置 API Key，点右上角 ⚙ 设置")

        # 组装：系统提示词 + 对话历史（只保留最近 12 轮，防止上下文无限膨胀）
        sys_prompt = build_system_prompt(ctx)
        clean = []
        for m in messages[-16:]:
            role = m.get("role")
            content = m.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                clean.append({"role": role, "content": content[:8000]})
        full = [{"role": "system", "content": sys_prompt}] + clean

        # ---- 建立 SSE 连接 ----
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        if is_mock:
            import random
            text = mock_stream_reply(clean, ctx)
            # 按标点/换行切块，模拟真实流式
            import re as _re
            pieces = _re.findall(r"[^\n]{1,18}|[\n]", text)
            for p in pieces:
                if not sse_event(self, {"type": "delta", "text": p}):
                    _chunked_end(self)
                    return
                time.sleep(0.012 + random.random() * 0.02)
            sse_event(self, {"type": "done", "model": cfg.get("model")})
            _chunked_end(self)
            return

        # ---- 真实模型 ----
        try:
            resp = self._llm_call(cfg, full, stream=True)
        except Exception as e:
            info = self._classify_llm_error(e)
            sse_event(self, {"type": "error",
                             "message": info["message"],
                             "kind": info["kind"],
                             "hint": info["hint"]})
            _chunked_end(self)
            return

        try:
            for raw_line in resp:
                line = raw_line.decode("utf-8", "replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    obj = json.loads(chunk)
                except Exception:
                    continue
                choices = obj.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                text = delta.get("content")
                if text:
                    if not sse_event(self, {"type": "delta", "text": text}):
                        break
            sse_event(self, {"type": "done", "model": cfg.get("model")})
        except Exception as e:
            sse_event(self, {"type": "error", "message": "读取流失败：%s" % e})
        finally:
            try:
                resp.close()
            except Exception:
                pass
            _chunked_end(self)

    # ---------- 静态 ----------
    def _static(self, rel):
        p = (STATIC / rel).resolve()
        try:
            p.relative_to(STATIC)
        except ValueError:
            return self._err(403, "越界")
        if not p.is_file():
            return self._err(404, "静态文件不存在: %s" % rel)
        ctype = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        if p.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"
        elif p.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        elif p.suffix in (".woff2", ".woff", ".ttf"):
            ctype = "font/" + p.suffix.lstrip(".")
        data = p.read_bytes()
        # vendor/ 下是第三方固定版本库（marked / KaTeX / hljs），文件名无哈希但内容永不变，
        # 可以长缓存；自己的文件（index.html / app.js / roadmap.js / style.css）文件名不带
        # 版本号，一旦长缓存就会一直发旧内容 —— 必须禁止缓存。之前统一 max-age=86400，
        # 导致改完 roadmap.js 后浏览器 24 小时内还在用旧版。
        rel_posix = rel.replace("\\", "/")
        static_like = p.suffix.lower() in (
            ".ico", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg",
            ".woff", ".woff2", ".ttf", ".eot")
        if rel_posix.startswith("vendor/") or static_like:
            cache = "public, max-age=604800"
        else:
            cache = "no-store, no-cache, must-revalidate, max-age=0"
        return self._send(200, data, ctype, {"Cache-Control": cache})

    # ---------- 按目录结构提供文件（支持 HTML 多页站点的相对导航）----------
    def _serve_file(self, rel):
        p = safe_path(rel)
        if not p.is_file():
            return self._err(404, "文件不存在")
        size = p.stat().st_size
        if size > MAX_RAW:
            return self._err(413, "文件过大")
        ctype = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        low = p.suffix.lower()
        if low in (".html", ".htm"):
            # HTML 用 UTF-8 解码，避免 GBK 误判导致中文乱码
            ctype = "text/html; charset=utf-8"
        elif low == ".js":
            ctype = "application/javascript; charset=utf-8"
        elif low == ".css":
            ctype = "text/css; charset=utf-8"
        elif low == ".svg":
            ctype = "image/svg+xml"
        elif low == ".pdf":
            ctype = "application/pdf"

        data = p.read_bytes()
        # 本地服务，缓存没有收益；课程文件重新导入后必须立刻生效
        self._send(200, data, ctype,
                   {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
                   gzip_ok=(low not in (".png", ".jpg", ".jpeg", ".gif", ".webp",
                                        ".woff", ".woff2", ".zip", ".pdf")))

    # ---------- API ----------
    def _api_stats(self):
        # 遍历 8000+ 文件较慢，缓存 10 分钟
        now = time.time()
        cached = _stats_cache.get("data")
        if cached and now - _stats_cache.get("ts", 0) < 600:
            return self._json(cached)

        secs = []
        total_files = 0
        total_size = 0
        for e in sorted(os.scandir(ROOT), key=lambda x: x.name):
            if not e.is_dir() or e.name in SKIP_DIRS or e.name.startswith("_"):
                continue
            d, f = list_dir(Path(e.path))
            sz = 0
            n = 0
            for root_, dirs_, files_ in os.walk(e.path):
                dirs_[:] = [d for d in dirs_ if d not in SKIP_DIRS and not d.startswith(".")]
                for fn in files_:
                    if fn.startswith("."):
                        continue
                    try:
                        sz += os.path.getsize(os.path.join(root_, fn))
                        n += 1
                    except OSError:
                        pass
            total_files += n
            total_size += sz
            secs.append({"name": e.name, "path": e.name,
                         "files": n, "size": sz, "repos": len(d)})
        data = {
            "root": str(ROOT),
            "sections": secs,
            "totalFiles": total_files,
            "totalSize": total_size,
        }
        _stats_cache["data"] = data
        _stats_cache["ts"] = now
        return self._json(data)

    def _api_tree(self):
        rel = self._q("path", "")
        p = safe_path(rel)
        if not p.exists():
            return self._err(404, "目录不存在")
        if not p.is_dir():
            return self._err(400, "不是目录")
        dirs, files = list_dir(p)
        parent = None
        if p != ROOT:
            parent = rel_of(p.parent)
        return self._json({
            "path": rel_of(p) if p != ROOT else "",
            "name": p.name or str(ROOT),
            "parent": parent,
            "dirs": dirs,
            "files": files,
            "counts": {"dirs": len(dirs), "files": len(files)},
        })

    def _api_file(self):
        rel = self._q("path", "")
        p = safe_path(rel)
        if not p.is_file():
            return self._err(404, "文件不存在")
        st = p.stat()
        name = p.name
        kind, lang, renderable = classify(name, st.st_size)
        meta = {
            "path": rel_of(p), "name": name, "size": st.st_size,
            "mtime": int(st.st_mtime), "ext": get_ext(name),
            "kind": kind, "language": lang, "renderable": renderable,
        }
        if st.st_size > MAX_TEXT:
            meta["content"] = None
            meta["reason"] = "文件过大（%.1f MB），超过文本上限 %.0f MB" % (
                st.st_size / 1048576, MAX_TEXT / 1048576)
            return self._json(meta)
        try:
            text = p.read_text(encoding="utf-8")
            meta["encoding"] = "utf-8"
        except UnicodeDecodeError:
            try:
                text = p.read_text(encoding="gbk", errors="replace")
                meta["encoding"] = "gbk"
            except Exception:
                text = None
                meta["reason"] = "无法以文本方式解码"
        meta["content"] = text
        return self._json(meta)

    def _api_raw(self):
        """原始字节流，支持 Range（PDF / 图片 / 大文件）"""
        rel = self._q("path", "")
        p = safe_path(rel)
        if not p.is_file():
            return self._err(404, "文件不存在")
        size = p.stat().st_size
        if size > MAX_RAW:
            return self._err(413, "文件过大（%.1f MB），请用系统程序打开" % (size / 1048576))

        ctype = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        if p.suffix.lower() == ".pdf":
            ctype = "application/pdf"
        elif p.suffix.lower() == ".svg":
            ctype = "image/svg+xml"

        start, end = 0, size - 1
        rng = self.headers.get("Range")
        partial = False
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                if m.group(2):
                    end = int(m.group(2))
                end = min(end, size - 1)
                if start <= end:
                    partial = True

        length = end - start + 1
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        # 图片/字体可短缓存（避免每次翻页重新解码）；文本类不缓存，改了立刻生效
        img_like = ctype.startswith("image/") or ctype.startswith("font/")
        self.send_header("Cache-Control",
                         "public, max-age=3600" if img_like
                         else "no-store, no-cache, must-revalidate, max-age=0")
        if partial:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.end_headers()
        try:
            with open(p, "rb") as f:
                f.seek(start)
                remain = length
                while remain > 0:
                    chunk = f.read(min(262144, remain))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remain -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _api_search(self):
        q = self._q("q", "").strip()
        if len(q) < 2:
            return self._json({"query": q, "count": 0, "results": [],
                               "error": "关键词至少 2 个字符"})
        try:
            limit = min(int(self._q("limit", str(SEARCH_LIMIT))), 500)
        except ValueError:
            limit = SEARCH_LIMIT
        return self._json(do_search(q, limit))


# ---------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------
def find_port(start=PORT, tries=20):
    for p in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((HOST, p))
                return p
            except OSError:
                continue
    raise RuntimeError("找不到可用端口 %d~%d" % (start, start + tries))


def main():
    if not ROOT.is_dir():
        print("!! 资料根目录不存在: %s" % ROOT)
        sys.exit(1)
    if not (STATIC / "index.html").is_file():
        print("!! 前端缺失: %s" % (STATIC / "index.html"))
        sys.exit(1)

    port = find_port()
    url = "http://%s:%d/" % (HOST, port)

    srv = ThreadingHTTPServer((HOST, port), Handler)
    srv.daemon_threads = True

    print("=" * 62)
    print("  agent学习平台 · 本地服务")
    print("=" * 62)
    print("  资料目录 : %s" % ROOT)
    print("  访问地址 : %s" % url)
    print("  监听     : %s:%d  (仅本机可访问)" % (HOST, port))
    print()
    print("  按 Ctrl+C 停止服务")
    print("=" * 62)

    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  正在停止 ...")
    finally:
        srv.shutdown()
        srv.server_close()
        print("  已停止")


if __name__ == "__main__":
    # 保证控制台中文正常
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
