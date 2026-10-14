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

        return self._err(404, "未知路径: %s" % path)

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
