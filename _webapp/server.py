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
import secrets
import threading
import webbrowser
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ---------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------
# 资料根目录：默认是仓库根（本文件所在目录的上一层），可用 STUDYAI_ROOT 环境变量覆盖。
# 这样克隆到任意路径都能直接跑，不用改代码。
_DEFAULT_ROOT = Path(__file__).resolve().parent.parent
ROOT     = Path(os.environ.get("STUDYAI_ROOT") or _DEFAULT_ROOT).resolve()
WEBAPP   = Path(__file__).resolve().parent
from app import ai, courses, ide, library


def _migrate_legacy_paths():
    """老版本把配置放在 _webapp 根下，这里自动搬到 data/（一次性）。"""
    data = WEBAPP / "data"
    data.mkdir(exist_ok=True)
    for old, new in ((WEBAPP / ".ai-config.json", data / "ai-config.json"),
                     (WEBAPP / ".lan-token", data / "lan-token"),
                     (WEBAPP / ".ide-config.json", data / "ide-config.json")):
        try:
            if old.is_file() and not new.exists():
                os.replace(old, new)
        except OSError:
            pass


_migrate_legacy_paths()

STATIC   = WEBAPP / "static"

HOST     = "127.0.0.1"
PORT     = 8777

# ---- 局域网模式（启动加 --lan 打开）----
# 电脑版照旧走 127.0.0.1，不需要令牌；
# 手机等外部设备必须带令牌，见启动时打印的 ?t= 地址。
LAN_MODE       = False
LAN_TOKEN      = ""
LAN_TOKEN_FILE = WEBAPP / "data" / "lan-token"


def load_or_create_lan_token():
    """读令牌；没有就生成一个存盘（.lan-token 已在 .gitignore）。"""
    try:
        if LAN_TOKEN_FILE.is_file():
            t = LAN_TOKEN_FILE.read_text(encoding="utf-8").strip()
            if t:
                return t
    except Exception:
        pass
    t = secrets.token_urlsafe(12)
    try:
        LAN_TOKEN_FILE.write_text(t, encoding="utf-8")
    except Exception:
        pass
    return t


def guess_lan_ip():
    """推断本机局域网 IP（UDP connect 不发包）。"""
    try:
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        u.connect(("8.8.8.8", 80))
        ip = u.getsockname()[0]
        u.close()
        return ip
    except Exception:
        return "127.0.0.1"

MAX_TEXT      = 8  * 1024 * 1024      # 文本类文件读取上限 8 MB
MAX_RAW       = 64 * 1024 * 1024      # 原始字节流上限 64 MB
SEARCH_LIMIT  = 200                   # 搜索最大结果数
SEARCH_MAXSIZE= 2  * 1024 * 1024      # 单文件搜索上限

# ---------------------------------------------------------------------
# AI 陪读配置（实现在 app/ai.py）
# ---------------------------------------------------------------------

AI_PRESETS          = ai.AI_PRESETS
AI_CONFIG_DEFAULT   = ai.AI_CONFIG_DEFAULT
AI_CONFIG_FILE      = ai.AI_CONFIG_FILE
load_ai_config      = ai.load_ai_config
save_ai_config      = ai.save_ai_config
mask_key            = ai.mask_key
build_system_prompt = ai.build_system_prompt
mock_stream_reply   = ai.mock_stream_reply
_ai_lock            = ai.LOCK

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
    ".github", ".vscode", ".idea", "_webapp", "_zips", "_scripts", "_dev",
    "_IDM导入清单", ".pytest_cache", "dist", "build", ".mypy_cache",
}

# /files/ 与 /api/raw 是「按真实路径取文件」，不受 SKIP_DIRS 约束 ——
# 于是 /files/_webapp/.ai-config.json 能把明文 API Key 直接下载走。
# 这里单独列一份「绝不对外」的名单，只拦工具/配置目录与密钥文件；
# 注意不要一刀切禁止所有点开头的目录：书库的 .preview 临时预览要靠 /files/ 打开。
DENY_SEGMENTS = {
    ".git", ".github", ".vscode", ".idea", "__pycache__", "node_modules",
    "_webapp", "_logs", "_build", "_shots", "_scripts", "_zips",
    "_agent-study-src", "_IDM导入清单", "_dev",
}
DENY_FILES = {
    ".ai-config.json", ".ai-config.tmp", ".lan-token",
    ".env", ".env.local",
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


def check_public(rel: str) -> Path:
    """safe_path + 敏感文件过滤，用于「按路径取文件」的路由。

    safe_path 只保证不越出 ROOT；但 ROOT 里本身就躺着密钥、令牌和 .git，
    所以对外提供文件前还要过一遍黑名单。
    """
    p = safe_path(rel)
    try:
        parts = p.relative_to(ROOT).parts
    except ValueError:
        raise UnsafePath("outside root: %s" % rel)
    for seg in parts:
        if seg.lower() in DENY_SEGMENTS:
            raise UnsafePath("blocked dir: %s" % rel)
    if parts and parts[-1].lower() in DENY_FILES:
        raise UnsafePath("blocked file: %s" % rel)
    return p


# ---------------------------------------------------------------------
# 给 HTML 注入 KaTeX
# ---------------------------------------------------------------------
# 用户放的 HTML 常常是自己用 Markdown 转的，里面写着 $...$ 但没引 MathJax。
# 直接放 iframe 只会看到一堆美元符号，所以这里把本地的 KaTeX 塞进去。
_KATEX_HEAD = (
    '<link rel="stylesheet" href="/static/vendor/katex.min.css">'
    '<script src="/static/vendor/katex.min.js"></script>'
    '<script src="/static/vendor/auto-render.min.js"></script>'
)

_KATEX_TAIL = """
<script>
(function () {
  function run() {
    if (!window.renderMathInElement) return;
    try {
      window.renderMathInElement(document.body, {
        delimiters: [
          { left: '$$', right: '$$', display: true },
          { left: '$',  right: '$',  display: false },
          { left: '\\\\(', right: '\\\\)', display: false },
          { left: '\\\\[', right: '\\\\]', display: true }
        ],
        ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'],
        throwOnError: false
      });
    } catch (e) { console.warn('KaTeX 渲染失败', e); }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else { run(); }
})();
</script>
"""


def inject_math_support(data: bytes) -> bytes:
    """把 KaTeX 注入 HTML，返回新的字节流。

    · 已经引过 katex 的页面原样返回，不重复注入
    · 优先插在 </head> 前；没有 head 就插在 <body 前；再没有就放最前面
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("gbk", errors="replace")
        except Exception:
            return data

    # 判断「已经引过 KaTeX」要看真实的 script/link，不能只看正文里有没有 katex 这个词，
    # 否则讲义里提一句 KaTeX 就再也不会注入公式渲染。
    if re.search(r"katex\.min\.(?:js|css)|renderMathInElement|/katex/", text, re.I):
        return data

    low = text.lower()
    if "</head>" in low:
        i = low.index("</head>")
        text = text[:i] + _KATEX_HEAD + text[i:]
    elif "<body" in low:
        i = low.index("<body")
        text = text[:i] + _KATEX_HEAD + text[i:]
    else:
        text = _KATEX_HEAD + text

    low = text.lower()
    if "</body>" in low:
        i = low.rindex("</body>")
        text = text[:i] + _KATEX_TAIL + text[i:]
    else:
        text = text + _KATEX_TAIL

    return text.encode("utf-8")


# ---------------------------------------------------------------------
# 目录树
# ---------------------------------------------------------------------
def list_dir(p: Path):
    dirs, files = [], []
    try:
        with os.scandir(p) as it:
            entries = list(it)
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
                    with os.scandir(e.path) as sub:
                        has_kids = any(True for _ in sub)
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

# ---------------------------------------------------------------------
# 自动退出（「关掉网页，后台也跟着走」）
# ---------------------------------------------------------------------
# 页面每隔十几秒发一次心跳；关掉标签页时用 sendBeacon 报个 bye。
# 最后一个页面走掉后再等 grace 秒还没人回来，就退出进程。
# 关掉这个功能（默认关）时完全不影响原有行为。
AUTO_EXIT = {
    "enabled": False,
    "grace": 20.0,      # 秒
    "since": None,      # 最后一个页面离开的时刻
    "clients": set(),   # 还在线的页面 sid
}
_SRV = {"srv": None}
_stats_cache  = {"ts": 0, "data": None}
# 缓存由多个请求线程共享，加锁避免并发时重复全量扫描（也避免半成品被读走）
_cache_lock = threading.Lock()

SEARCHABLE = {"markdown", "notebook", "code", "text"}


def build_index():
    now = time.time()
    if now - _search_cache["ts"] < 300 and _search_cache["index"]:
        return _search_cache["index"]
    with _cache_lock:
        # 双重检查：可能别的线程已经建好了
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
        # 先读字节再解码：中文资料不一定是 UTF-8，GBK 编码的直接按 UTF-8 读会整篇变空、
        # 搜索静默漏掉（errors="ignore" 会把非法字节全丢掉）。
        try:
            raw = fp.read_bytes()
        except OSError:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("gbk", errors="ignore")
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


def compute_stats():
    """扫描根目录，统计每个板块的文件数与体积（跳过 SKIP_DIRS 与隐藏项）。"""
    secs = []
    total_files = 0
    total_size = 0
    with os.scandir(ROOT) as it:
        entries = sorted(it, key=lambda x: x.name)
    for e in entries:
        if not e.is_dir() or e.name in SKIP_DIRS or e.name.startswith("_"):
            continue
        d, f = list_dir(Path(e.path))
        sz = 0
        n = 0
        for root_, dirs_, files_ in os.walk(e.path):
            dirs_[:] = [x for x in dirs_ if x not in SKIP_DIRS and not x.startswith(".")]
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
    return {
        "root": str(ROOT),
        "sections": secs,
        "totalFiles": total_files,
        "totalSize": total_size,
    }


# ---------------------------------------------------------------------
# HTTP 处理
# ---------------------------------------------------------------------
CT_JSON = "application/json; charset=utf-8"


class Handler(BaseHTTPRequestHandler):
    server_version = "agent-study-platform/1.0"
    protocol_version = "HTTP/1.1"
    _head_only = False

    def log_message(self, fmt, *args):
        # 静音常规请求，只留 4xx / 5xx。
        # log_request 传的是 (请求行, 状态码, 长度)，log_error 传的是 (状态码, 消息)，
        # 状态码可能落在 args[0] 也可能落在 args[1] —— 只判 args[0] 会永远不命中。
        code = None
        for a in args[:2]:
            s = str(a)
            if len(s) == 3 and s.isdigit() and s[0] in "45":
                code = s
                break
        if not code:
            return
        try:
            text = fmt % args
        except Exception:
            text = fmt
        sys.stderr.write("  [%s] %s %s\n" % (self.log_date_time_string(), code, text))
        sys.stderr.flush()

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
        if self._head_only:
            return
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

    # ---------- 访问控制（局域网模式） ----------
    def _client_is_local(self):
        """请求是否来自本机（回环地址）。本机永远放行，电脑版不受影响。"""
        try:
            ip = self.client_address[0]
        except Exception:
            return False
        return ip in ("127.0.0.1", "::1", "localhost")

    def _token_ok(self):
        """局域网访问必须带令牌：?t=xxx 或 cookie。"""
        if not LAN_MODE or self._client_is_local():
            return True
        want = LAN_TOKEN
        if not want:
            return True
        # 1) 查询串 ?t=
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        got = (qs.get("t") or [""])[0]
        if got and secrets.compare_digest(got, want):
            return True
        # 2) Cookie
        cookie = self.headers.get("Cookie") or ""
        m = re.search(r"(?:^|;\s*)smk=([^;]+)", cookie)
        if m and secrets.compare_digest(m.group(1), want):
            return True
        return False

    def _reject_unauth(self):
        body = (
            "<!doctype html><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<body style=\"font:16px/1.8 -apple-system,system-ui,sans-serif;"
            "padding:28px;color:#333;max-width:520px;margin:auto\">"
            "<h2 style='margin:0 0 10px'>需要访问令牌</h2>"
            "<p style='color:#666'>这个服务只允许本机或带令牌的设备访问。</p>"
            "<p style='color:#666'>请复制电脑上服务窗口打印的完整地址（带 "
            "<code>?t=</code> 的那一串）再打开。</p>"
            "</body>"
        ).encode("utf-8")
        self.send_response(403)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self._head_only:
            return
        try:
            self.wfile.write(body)
        except Exception:
            pass

    # ---------- 路由 ----------
    def do_GET(self):
        try:
            if not self._token_ok():
                return self._reject_unauth()
            return self._route()
        except UnsafePath as e:
            return self._err(403, "路径越界: %s" % e)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._err(500, "%s: %s" % (type(e).__name__, e))

    def do_HEAD(self):
        # HEAD 只要头部。直接复用 do_GET 会把 body 也写出去，
        # 声明了 Content-Length 却又多发一份字节，keep-alive 上的下一个请求就会错位。
        self._head_only = True
        try:
            return self.do_GET()
        finally:
            self._head_only = False

    def _route(self):
        path = urllib.parse.urlparse(self.path).path

        if path in ("/", "/index.html"):
            return self._static("index.html")

        # 手机版外壳（与电脑版共用渲染器与陪读逻辑，布局独立）
        if path in ("/m", "/m/", "/m/index.html"):
            return self._static("m/index.html")

        # 动画介绍片（自动播放的分镜页，视频的替代）
        if path in ("/film", "/film/", "/film/index.html"):
            return self._static("showcase/film.html")
        # 产品展示页（对外介绍用的静态单页）
        if path in ("/showcase", "/showcase/", "/showcase/index.html"):
            return self._static("showcase/index.html")

        # 代码编辑器（Monaco，只读预览）
        if path in ("/ide", "/ide/", "/ide/index.html"):
            return self._static("ide/index.html")

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

        # 与 /files/ 相同，但给 HTML 注入 KaTeX（公式渲染）
        if path.startswith("/mathfiles/"):
            return self._serve_file(urllib.parse.unquote(path[len("/mathfiles/"):]), inject_math=True)

        # ---- 练习区（保存 / 运行；--ide 才挂载）----
        if path.startswith("/api/ide/"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return ide.handle(self, path, q)

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
            return self._json({"ok": True, "root": str(ROOT), "autoExit": AUTO_EXIT["enabled"]})

        # ---- 存活心跳（用于自动退出）----
        if path == "/api/heartbeat":
            sid = self._q("sid", "")
            if sid:
                AUTO_EXIT["clients"].add(sid)
                AUTO_EXIT["since"] = None
            return self._json({"ok": True, "clients": len(AUTO_EXIT["clients"])})

        if path == "/api/bye":
            sid = self._q("sid", "")
            if sid:
                AUTO_EXIT["clients"].discard(sid)
            if not AUTO_EXIT["clients"]:
                AUTO_EXIT["since"] = time.time()
            return self._json({"ok": True, "clients": len(AUTO_EXIT["clients"])})

        # ---- 课程包（校验通过才出现在列表里）----
        if path.startswith("/api/courses"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return courses.handle(self, path, q)

        # ---- 用户书库（--library 时才启用，默认不接管任何路由）----
        # 没启用时也给前端一个明确答复，别让它每次开页都收一条 404（控制台噪音）
        if path == "/api/library/info" and not library.ENABLED:
            return self._json({"enabled": False})
        if library.ENABLED and path.startswith("/api/library/"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return library.handle(self, path, q)
        if library.ENABLED and path in ("/library", "/library/", "/library/index.html"):
            return self._static("mybooks/index.html")

        # ---- AI 陪读 ----
        if path == "/api/ai/config":
            return self._api_ai_config_get()
        if path == "/api/ai/presets":
            return self._json({"presets": AI_PRESETS})

        return self._err(404, "未知路径: %s" % path)

    # ---------- POST ----------
    def do_POST(self):
        try:
            if not self._token_ok():
                return self._reject_unauth()
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
        if path.startswith("/api/ide/"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return ide.handle(self, path, q)
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
        if n <= limit:
            return self.rfile.read(n)
        # 超限：只取前 limit 字节，但剩下的必须读掉。
        # 否则残留字节会被当成下一个请求的开头，keep-alive 连接直接串包。
        data = self.rfile.read(limit)
        remain = n - limit
        if remain > 8 * 1024 * 1024:
            # 剩太多就不为一条坏请求耗带宽，直接断开这条连接
            self.close_connection = True
            return data
        while remain > 0:
            chunk = self.rfile.read(min(65536, remain))
            if not chunk:
                break
            remain -= len(chunk)
        return data

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
            reply = ai.llm_call(cfg, [{"role": "user", "content": "只回复两个字：你好"}],
                                   stream=False, max_tokens=16)
        except Exception as e:
            info = ai.classify_error(e)
            info.update({"ok": False, "error": info.pop("message")})
            return self._json(info, 200)
        return self._json({
            "ok": True,
            "ms": int((time.time() - t0) * 1000),
            "reply": (reply or "")[:60],
            "model": cfg.get("model"),
        })

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
            resp = ai.llm_call(cfg, full, stream=True)
        except Exception as e:
            info = ai.classify_error(e)
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
    def _serve_file(self, rel, inject_math=False):
        p = check_public(rel)
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

        # /mathfiles/ 走这条路：给 HTML 注入 KaTeX，让它里面的 $...$ 也能渲染成公式。
        # 用路径前缀而不是查询参数，是因为页内相对链接跳转时会丢掉 query。
        if inject_math and low in (".html", ".htm"):
            data = inject_math_support(data)
            ctype = "text/html; charset=utf-8"

        # 本地服务，缓存没有收益；课程文件重新导入后必须立刻生效
        self._send(200, data, ctype,
                   {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
                   gzip_ok=(low not in (".png", ".jpg", ".jpeg", ".gif", ".webp",
                                        ".woff", ".woff2", ".zip", ".pdf")))

    # ---------- API ----------
    def _api_stats(self):
        # 遍历全库较慢，缓存 10 分钟；并发请求只让一个线程真正去扫
        cached = _stats_cache.get("data")
        if cached and time.time() - _stats_cache.get("ts", 0) < 600:
            return self._json(cached)
        with _cache_lock:
            data = _stats_cache.get("data")
            if not data or time.time() - _stats_cache.get("ts", 0) >= 600:
                data = compute_stats()
                _stats_cache["data"] = data
                _stats_cache["ts"] = time.time()
        return self._json(data)

    def _api_tree(self):
        rel = self._q("path", "")
        p = check_public(rel)
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
        p = check_public(rel)
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
        # BOM 必须剥掉：Windows 记事本 / Set-Content / Excel 导出常带 UTF-8 BOM，
        # 留着会让第一行变成 "\ufeff# 标题"，Markdown 认不出这是标题。
        if text and text.startswith("\ufeff"):
            text = text[1:]
            meta["bom"] = True
        meta["content"] = text
        return self._json(meta)

    def _api_raw(self):
        """原始字节流，支持 Range（PDF / 图片 / 大文件）"""
        rel = self._q("path", "")
        p = check_public(rel)
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
        rng = (self.headers.get("Range") or "").strip()
        partial = False
        if rng:
            # RFC 7233：bytes=a-b 闭区间；bytes=a- 到尾；bytes=-n 是「最后 n 字节」。
            # 旧写法把 bytes=-n 当成 0-n，PDF 恢复阅读位置 / 断点续传会拿到文件开头。
            m = re.match(r"^bytes=(\d*)-(\d*)$", rng)
            if not m or (not m.group(1) and not m.group(2)):
                return self._range_unsatisfiable(size)
            if not m.group(1):
                n = int(m.group(2))
                if n <= 0:
                    return self._range_unsatisfiable(size)
                start = max(0, size - n)
                end = size - 1
            else:
                start = int(m.group(1))
                if start >= size:
                    return self._range_unsatisfiable(size)
                end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
                if end < start:
                    return self._range_unsatisfiable(size)
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
        if self._head_only:
            return
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

    def _range_unsatisfiable(self, size):
        """区间不合法时按 RFC 返回 416，而不是 200 + 空 body（后者会被当成 0 字节文件）。"""
        self.send_response(416)
        self.send_header("Content-Range", "bytes */%d" % size)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

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
class StudyServer(ThreadingHTTPServer):
    daemon_threads = True
    # Windows 的 SO_REUSEADDR 语义与 Linux 不同：它允许两个进程绑同一端口，
    # 于是「端口被占用就顺延」完全失效，还会堆出收不到请求的幽灵实例。
    # 所以 Windows 下必须关掉端口复用。
    allow_reuse_address = (os.name != "nt")


def find_port(start=PORT, tries=20):
    for p in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if os.name != "nt":
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((HOST, p))
                return p
            except OSError:
                continue
    raise RuntimeError("找不到可用端口 %d~%d" % (start, start + tries))


def _port_is_free(port):
    """快速判断端口有没有人在听（bind 是瞬时的，不像 connect 那样要等超时）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, port))
            return True
        except OSError:
            return False


def already_running():
    """默认端口段上已经有「同一个资料根」的实例在跑吗？有就返回它的地址。

    注意不要盲目对 20 个端口发 HTTP 请求：Windows 上连一个没人监听的端口
    要等 0.3 秒左右，20 个就是 6~8 秒，启动会明显变慢，还会让并发启动互相抢端口。
    所以先用 bind 瞬时筛出「确实被占用」的端口，再只对它们发 ping。
    """
    import urllib.request
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    want = str(ROOT).lower()
    for p in range(PORT, PORT + 20):
        if _port_is_free(p):
            continue
        try:
            with opener.open("http://127.0.0.1:%d/api/ping" % p, timeout=0.5) as r:
                obj = json.loads(r.read().decode("utf-8", "replace"))
        except Exception:
            continue
        if obj.get("ok") and str(obj.get("root", "")).lower() == want:
            return "http://127.0.0.1:%d/" % p
    return None


def main():
    global HOST, LAN_MODE, LAN_TOKEN

    if not ROOT.is_dir():
        print("!! 资料根目录不存在: %s" % ROOT)
        sys.exit(1)
    if not (STATIC / "index.html").is_file():
        print("!! 前端缺失: %s" % (STATIC / "index.html"))
        sys.exit(1)

    # --- 自动退出 ---
    # --auto-exit        默认空闲 20 秒后退出
    # --auto-exit=60     自定义宽限秒数
    # 由「资源管理器右键」启动时自动带上，手动启动默认不带。
    for a in sys.argv[1:]:
        if a == "--auto-exit":
            AUTO_EXIT["enabled"] = True
        elif a.startswith("--auto-exit="):
            try:
                AUTO_EXIT["grace"] = max(5.0, float(a.split("=", 1)[1]))
                AUTO_EXIT["enabled"] = True
            except ValueError:
                pass

    # --- 课程包校验（始终启用，只读）---
    courses.configure(ROOT, library.LIB_DIRNAME)

    # --- 用户书库（独立功能，默认关闭）---
    if "--library" in sys.argv:
        library.ENABLED = True
        library.configure(ROOT, classify)
        _lib = library.lib_dir(create=True)
        print("  书库     : %s" % _lib)

    # --- 局域网模式 ---
    if "--lan" in sys.argv:
        LAN_MODE = True
        LAN_TOKEN = load_or_create_lan_token()
        HOST = "0.0.0.0"

    # --bind <IP>：额外在指定网卡上开一个监听（比如 USB 共享网络的地址）。
    # 这样既保留 127.0.0.1，又能让手机通过 USB 访问，且完全不开 0.0.0.0，
    # WiFi 上的其他设备碰不到。
    extra_binds = []
    for i, a in enumerate(sys.argv):
        if a == "--bind" and i + 1 < len(sys.argv):
            ip = sys.argv[i + 1].strip()
            if ip and ip != "127.0.0.1" and ip != "0.0.0.0":
                extra_binds.append(ip)
        elif a.startswith("--bind="):
            ip = a.split("=", 1)[1].strip()
            if ip and ip != "127.0.0.1" and ip != "0.0.0.0":
                extra_binds.append(ip)

    # 已经在跑就不再起第二个：Windows 下重复实例会静默绑同一端口，
    # 变成收不到请求的幽灵进程，还会让「改了代码重启」看起来没生效。
    if not any(a in ("--lan", "--force") or a.startswith("--bind") for a in sys.argv[1:]):
        running = already_running()
        if running:
            print("  服务已在运行：%s" % running)
            if "--no-browser" not in sys.argv:
                webbrowser.open(running)
            print("  这次不再启动新实例（旧的还在服务）。要强制重启请加 --force")
            return

    # --- 练习区（保存文件 + 运行代码，默认关闭）---
    # ROOT 必须先给 ide，哪怕没开 --ide：/api/ide/status 是不受 ENABLED 限制的那一个，
    # 前端打开编辑器页时一定会调它。不 configure 就会在 status() 里拿 None 做路径运算 → 500，
    # 用户看到的是"服务器错误"而不是"IDE 未启用"。
    ide.configure(ROOT)
    if "--ide" in sys.argv:
        if LAN_MODE or extra_binds:
            print("!! --ide 不能和 --lan / --bind 同时用：")
            print("   那等于把「任意代码执行」开放给局域网，风险太高。")
            sys.exit(1)
        ide.ENABLED = True

    port = find_port()
    local_url = "http://127.0.0.1:%d/" % port

    try:
        srv = StudyServer((HOST, port), Handler)
    except OSError as e:
        print("!! 端口 %d 绑定失败：%s" % (port, e))
        sys.exit(1)
    _SRV["srv"] = srv

    def _cleanup_previews():
        """退出前清掉没人要的预览文件。

        「要不要保存」已经挪到网页里问了（顶部提示条），
        所以这里只负责：没点保存的，一律删掉 —— 这就是「不导入就退」。
        """
        import shutil as _sh
        base = ROOT / library.LIB_DIRNAME / ".preview"
        if not base.is_dir():
            return
        try:
            n = sum(1 for d in base.rglob("*") if d.is_file())
        except OSError:
            n = 0
        try:
            _sh.rmtree(str(base), ignore_errors=True)
        except Exception:
            pass
        if n:
            print("  清理临时预览 %d 个文件" % n)
    if AUTO_EXIT["enabled"]:
        def _watchdog():
            while True:
                time.sleep(2.0)
                since = AUTO_EXIT["since"]
                if since is None:
                    continue
                idle = time.time() - since
                if idle >= AUTO_EXIT["grace"]:
                    print("  页面已全部关闭，%.0f 秒无连接，准备退出" % idle)
                    try:
                        _cleanup_previews()
                    except Exception as _e:
                        print("  预览清理失败: %s" % _e)
                    try:
                        srv.shutdown()
                    except Exception:
                        pass
                    os._exit(0)

        threading.Thread(target=_watchdog, daemon=True).start()

    # 额外的监听：同一个端口，绑到别的网卡上
    extra_srvs = []
    for ip in extra_binds:
        try:
            s2 = StudyServer((ip, port), Handler)
            extra_srvs.append((ip, s2))
        except Exception as e:
            print("!! 无法绑定 %s:%d —— %s" % (ip, port, e))

    print("=" * 62)
    print("  agent学习平台 · 本地服务")
    print("=" * 62)
    print("  资料目录 : %s" % ROOT)
    if ide.ENABLED:
        _st = ide.status()
        print("  练习区   : %s" % _st["workspaceAbs"])
        print("  解释器   : %s" % _st["python"])
    print("  本机访问 : %s" % local_url)
    if LAN_MODE:
        ip = guess_lan_ip()
        print("  手机访问 : http://%s:%d/m?t=%s" % (ip, port, LAN_TOKEN))
        print("  监听     : 0.0.0.0:%d  (局域网可访问，需令牌)" % port)
        print()
        print("  ⚠ 同一 WiFi 下的其他设备没有这个令牌就进不来。")
        print("    令牌存在 _webapp/.lan-token，想换就删掉它重启。")
    elif extra_srvs:
        for ip, _ in extra_srvs:
            print("  手机访问 : http://%s:%d/m" % (ip, port))
        print("  监听     : 127.0.0.1 + %s  (只在这些网卡上，不开 0.0.0.0)"
              % ", ".join(ip for ip, _ in extra_srvs))
        print()
        print("  这条链路只走你插的那根线，WiFi 上的其他设备碰不到。")
    else:
        print("  监听     : %s:%d  (仅本机可访问)" % (HOST, port))
        print()
        print("  想在手机/平板上用？")
        print("     USB 共享网络 : python server.py --bind <那块网卡的IP>")
        print("     同一 WiFi    : python server.py --lan   (带访问令牌)")
    print()
    print("  按 Ctrl+C 停止服务")
    print("=" * 62)

    # 额外监听放到后台线程
    for ip, s2 in extra_srvs:
        threading.Thread(target=s2.serve_forever, daemon=True).start()

    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(local_url)).start()

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
