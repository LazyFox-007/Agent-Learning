#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用户书库 —— 独立模块，与主目录树完全隔离。

设计原则
  · 不改 server.py 的现有逻辑（list_dir / safe_path / classify 一个都不动）
  · 所有路由挂在 /api/library/* 下
  · 书库目录独立（默认 书库/，已加进 .gitignore）
  · 默认关闭，启动时加 --library 才启用

启用
  python server.py --library

路由
  GET  /api/library/list?path=<相对路径>   列目录
  GET  /api/library/info                   书库状态
  POST /api/library/reveal                 在资源管理器里打开（仅本机）
"""

import json
import os
import shutil
import sys
import time
import urllib.parse
from pathlib import Path

# ---------------------------------------------------------------
# 配置（由 server.py 在启动时注入）
# ---------------------------------------------------------------
LIB_DIRNAME = "书库"
ENABLED = False

_root = None        # 资料根目录（server.ROOT）
_classify = None    # server.classify，复用现有的文件类型判断

# 允许用户放进来的扩展名。不在表里的也能读（复用主程序判断），
# 但这里是「上传」阶段的白名单，Phase 2 才会用到。
ALLOWED_EXT = {
    ".md", ".markdown", ".txt", ".html", ".htm", ".pdf",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg",
    ".ipynb", ".py", ".js", ".json", ".csv", ".yaml", ".yml",
    ".docx", ".epub",
}

# 书库里不显示的名字
SKIP_NAMES = {".trash", ".DS_Store", "Thumbs.db", "desktop.ini"}

# ---------------------------------------------------------------
# 「以……打开」—— 类比 VSCode 的 Open With
# ---------------------------------------------------------------
# 安全要点：浏览器只能传 app 的 id，命令一律由服务端固定，
# 绝不接受前端传来的可执行路径或参数。
TEXT_EXTS = {
    ".md", ".markdown", ".txt", ".html", ".htm", ".json", ".csv",
    ".py", ".js", ".css", ".yaml", ".yml", ".toml", ".ini", ".log",
    ".xml", ".sql", ".sh", ".bat", ".ps1", ".c", ".cpp", ".h", ".java",
}

APP_DEFS = [
    {"id": "default",  "label": "用系统默认程序打开", "icon": "↗",  "scope": "all"},
    {"id": "explorer", "label": "在资源管理器中显示", "icon": "📁", "scope": "all"},
    {"id": "vscode",   "label": "用 VSCode 打开",     "icon": "🧩", "scope": "text", "cmd": "code"},
    {"id": "notepad",  "label": "用记事本打开",       "icon": "📝", "scope": "text", "cmd": "notepad.exe"},
]


def available_apps(ext=""):
    """当前系统上真正可用的打开方式。"""
    import shutil
    ext = (ext or "").lower()
    out = []
    for a in APP_DEFS:
        if a["scope"] == "text" and ext not in TEXT_EXTS:
            continue
        if a.get("cmd") and not shutil.which(a["cmd"]):
            continue
        out.append({"id": a["id"], "label": a["label"], "icon": a["icon"]})
    return out


def open_with(rel, app_id):
    """用指定方式打开书库里的文件。只允许白名单里的 app_id。"""
    import shutil
    import subprocess

    target = safe_rel(rel)
    if not target.exists():
        raise FileNotFoundError("文件不存在: %s" % rel)

    # app_id 必须精确命中白名单
    spec = next((a for a in APP_DEFS if a["id"] == app_id), None)
    if spec is None:
        raise ValueError("不支持的打开方式: %s" % app_id)

    ext = target.suffix.lower()
    if spec["scope"] == "text" and ext not in TEXT_EXTS:
        raise ValueError("「%s」不支持这种文件类型" % spec["label"])

    path = str(target)

    if app_id == "default":
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    elif app_id == "explorer":
        if sys.platform != "win32":
            raise ValueError("「在资源管理器中显示」仅支持 Windows")
        # /select 后面必须紧跟逗号，且路径作为独立参数传入
        subprocess.Popen(["explorer", "/select,%s" % path])

    elif app_id == "vscode":
        exe = shutil.which("code")
        if not exe:
            raise ValueError("找不到 VSCode 的 code 命令")
        subprocess.Popen([exe, "-g", path])

    elif app_id == "notepad":
        exe = shutil.which("notepad.exe")
        if not exe:
            raise ValueError("找不到记事本")
        subprocess.Popen([exe, path])

    return {"ok": True, "opened": path, "app": app_id}



def configure(root, classify):
    """由 server.py 调用，注入依赖，避免循环 import。"""
    global _root, _classify
    _root = Path(root).resolve()
    _classify = classify


# ---------------------------------------------------------------
# 路径
# ---------------------------------------------------------------
class LibUnsafe(Exception):
    pass


def lib_dir(create=True):
    """书库根目录。create=True 时确保存在（含回收站）。"""
    if _root is None:
        raise RuntimeError("library.configure() 未被调用")
    p = _root / LIB_DIRNAME
    if create:
        p.mkdir(parents=True, exist_ok=True)
        (p / ".trash").mkdir(parents=True, exist_ok=True)
    return p


def safe_rel(rel):
    """把请求的相对路径解析到书库内部；越界抛 LibUnsafe。"""
    if rel is None:
        rel = ""
    rel = urllib.parse.unquote(str(rel)).replace("\\", "/").strip("/")
    if "\x00" in rel:
        raise LibUnsafe("NUL in path")
    base = lib_dir(create=False).resolve()
    p = (base / rel).resolve()
    try:
        p.relative_to(base)
    except ValueError:
        raise LibUnsafe("outside library: %s" % rel)
    return p


def rel_of(p):
    base = lib_dir(create=False).resolve()
    return str(Path(p).resolve().relative_to(base)).replace("\\", "/")


# ---------------------------------------------------------------
# 列目录
# ---------------------------------------------------------------
def scan(rel=""):
    """列出书库某目录的内容。返回与主程序 /api/tree 同构的结构。"""
    target = safe_rel(rel)
    if not target.exists():
        raise FileNotFoundError("目录不存在: %s" % rel)
    if not target.is_dir():
        raise NotADirectoryError("不是目录: %s" % rel)

    dirs, files = [], []
    try:
        entries = list(os.scandir(target))
    except (PermissionError, FileNotFoundError):
        return dirs, files

    for e in entries:
        name = e.name
        if name in SKIP_NAMES or name.startswith("."):
            continue
        try:
            if e.is_dir(follow_symlinks=False):
                try:
                    has_kids = any(True for _ in os.scandir(e.path))
                except OSError:
                    has_kids = False
                dirs.append({
                    "name": name,
                    "path": rel_of(e.path),
                    "type": "dir",
                    "hasChildren": has_kids,
                })
            elif e.is_file(follow_symlinks=False):
                st = e.stat()
                kind, lang, renderable = _classify(name, st.st_size)
                files.append({
                    "name": name,
                    "path": rel_of(e.path),
                    "type": "file",
                    "size": st.st_size,
                    "mtime": int(st.st_mtime),
                    "ext": os.path.splitext(name)[1].lower(),
                    "kind": kind,
                    "language": lang,
                    "renderable": renderable,
                    "allowed": os.path.splitext(name)[1].lower() in ALLOWED_EXT,
                })
        except OSError:
            continue

    dirs.sort(key=lambda x: x["name"].lower())

    # 书库支持手动排序：按 .order.json 里记的顺序，没记过的按名字
    by_name = {f["name"]: f for f in files}
    ordered = apply_order(rel, list(by_name.keys()))
    files = [by_name[n] for n in ordered]

    return dirs, files


# ---------------------------------------------------------------
# 临时预览：保存 or 丢弃
# ---------------------------------------------------------------
PREVIEW_DIR = ".preview"


def _in_preview(rel):
    p = (rel or "").replace("\\", "/")
    return (PREVIEW_DIR + "/") in p


def promote(rel):
    """把预览文件移到 书库/导入/。同名不覆盖。"""
    if not _in_preview(rel):
        raise ValueError("不是预览文件: %s" % rel)

    src = safe_rel(rel)
    if not src.is_file():
        raise FileNotFoundError("预览文件不存在: %s" % rel)

    import_dir = lib_dir(create=True) / "导入"
    import_dir.mkdir(parents=True, exist_ok=True)

    dest = import_dir / src.name
    i = 2
    while dest.exists():
        dest = import_dir / ("%s (%d)%s" % (src.stem, i, src.suffix))
        i += 1

    shutil.move(str(src), str(dest))
    _cleanup_preview_parent(src)
    return {"ok": True, "savedAs": rel_of(dest), "name": dest.name}


def discard(rel):
    """丢弃预览文件（连同它那层临时目录）。"""
    if not _in_preview(rel):
        raise ValueError("不是预览文件: %s" % rel)

    src = safe_rel(rel)
    if src.exists():
        try:
            src.unlink()
        except OSError:
            shutil.rmtree(str(src), ignore_errors=True)
    _cleanup_preview_parent(src)
    return {"ok": True, "discarded": src.name}


def _cleanup_preview_parent(p):
    """如果预览文件所在的临时目录空了，把它也删掉。"""
    root = lib_dir(create=False) / PREVIEW_DIR
    try:
        parent = Path(p).parent
        if parent == root or root not in parent.parents:
            return
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
        if root.is_dir() and not any(root.iterdir()):
            root.rmdir()
    except OSError:
        pass

# ---------------------------------------------------------------
# 手动排序（书库专用，课程不参与）
# ---------------------------------------------------------------
ORDER_FILE = ".order.json"


def _order_path():
    return lib_dir(create=False) / ORDER_FILE


def load_order():
    try:
        data = json.loads(_order_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_order(data):
    p = _order_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def apply_order(rel_dir, names):
    """按 .order.json 里记的顺序排；没记过的排后面，按名字排。"""
    seq = load_order().get(rel_dir or "")
    if not isinstance(seq, list):
        seq = []
    idx = {}
    for i, n in enumerate(seq):
        if isinstance(n, str):
            idx[n] = i
    big = 10 ** 6
    return sorted(names, key=lambda n: (idx.get(n, big), n.lower()))


def reorder(rel_dir, names):
    """保存某个目录下的文件顺序。只保留真实存在的文件。"""
    target = safe_rel(rel_dir)
    if not target.is_dir():
        raise NotADirectoryError("目录不存在: %s" % rel_dir)

    existing = set()
    for e in os.scandir(target):
        if e.is_file(follow_symlinks=False):
            existing.add(e.name)

    kept = [n for n in names if isinstance(n, str) and n in existing]
    for n in sorted(existing - set(kept), key=str.lower):
        kept.append(n)

    data = load_order()
    data[rel_dir or ""] = kept
    save_order(data)
    return kept


# ---------------------------------------------------------------
# 删除（移到 .trash，可恢复）
# ---------------------------------------------------------------
TRASH_DIR = ".trash"


def delete_entry(rel):
    """把书库里的文件/目录移到回收站，不做真删除。"""
    import datetime

    target = safe_rel(rel)
    base = lib_dir(create=False).resolve()

    if target == base:
        raise ValueError("不能删除书库根目录")
    if not target.exists():
        raise FileNotFoundError("文件不存在: %s" % rel)

    trash = base / TRASH_DIR
    trash.mkdir(exist_ok=True)

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = trash / ("%s__%s" % (stamp, target.name))
    i = 2
    while dest.exists():
        dest = trash / ("%s-%d__%s" % (stamp, i, target.name))
        i += 1

    shutil.move(str(target), str(dest))

    parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
    data = load_order()
    if parent in data and isinstance(data[parent], list):
        data[parent] = [n for n in data[parent] if n != target.name]
        save_order(data)

    return {"ok": True, "movedTo": str(dest), "name": target.name}

def stats():
    """书库概况：文件数、总大小、最近修改。"""
    base = lib_dir(create=True)
    n, total, latest = 0, 0, 0
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_NAMES and not d.startswith(".")]
        for fn in filenames:
            if fn in SKIP_NAMES or fn.startswith("."):
                continue
            try:
                st = (Path(dirpath) / fn).stat()
            except OSError:
                continue
            n += 1
            total += st.st_size
            latest = max(latest, int(st.st_mtime))
    return {
        "dir": str(base),
        "exists": base.is_dir(),
        "files": n,
        "bytes": total,
        "latest": latest,
    }


# ---------------------------------------------------------------
# 在资源管理器里打开
# ---------------------------------------------------------------
def reveal(rel=""):
    """打开书库目录。只允许本机调用 —— 局域网上的设备不能远程弹我的窗口。"""
    target = safe_rel(rel)
    if not target.exists():
        target = lib_dir(create=True)
    if target.is_file():
        target = target.parent

    if sys.platform == "win32":
        os.startfile(str(target))
    elif sys.platform == "darwin":
        import subprocess
        subprocess.Popen(["open", str(target)])
    else:
        import subprocess
        subprocess.Popen(["xdg-open", str(target)])
    return str(target)


# ---------------------------------------------------------------
# 路由
# ---------------------------------------------------------------
def handle(handler, path, query):
    """处理 /api/library/* 的 GET 请求。

    handler 是 server.Handler 实例，只用它已有的 _json / _err。
    """
    if path == "/api/library/info":
        s = stats()
        s["enabled"] = ENABLED
        s["dirName"] = LIB_DIRNAME
        return handler._json(s)

    if path == "/api/library/list":
        rel = (query.get("path") or [""])[0]
        try:
            dirs, files = scan(rel)
        except (LibUnsafe, FileNotFoundError, NotADirectoryError) as e:
            return handler._err(400, str(e))
        return handler._json({
            "path": rel,
            "dirs": dirs,
            "files": files,
        })

    if path == "/api/library/promote":
        rel = (query.get("path") or [""])[0]
        try:
            return handler._json(promote(rel))
        except (LibUnsafe, FileNotFoundError, ValueError) as e:
            return handler._err(400, str(e))
        except OSError as e:
            return handler._err(500, "保存失败: %s" % e)

    if path == "/api/library/discard":
        rel = (query.get("path") or [""])[0]
        try:
            return handler._json(discard(rel))
        except (LibUnsafe, ValueError) as e:
            return handler._err(400, str(e))

    if path == "/api/library/reorder":
        # GET 带 names=a,b,c 简化调用（前端不用发 POST）
        rel = (query.get("path") or [""])[0]
        raw = (query.get("names") or [""])[0]
        names = [n for n in raw.split("\x1f") if n] if "\x1f" in raw else [n for n in raw.split(",") if n]
        try:
            kept = reorder(rel, names)
        except (LibUnsafe, NotADirectoryError) as e:
            return handler._err(400, str(e))
        return handler._json({"ok": True, "order": kept})

    if path == "/api/library/delete":
        client = handler.client_address[0] if handler.client_address else ""
        if client not in ("127.0.0.1", "::1", "localhost"):
            return handler._err(403, "删除只能在运行服务的这台电脑上操作")
        rel = (query.get("path") or [""])[0]
        try:
            return handler._json(delete_entry(rel))
        except (LibUnsafe, FileNotFoundError, ValueError) as e:
            return handler._err(400, str(e))
        except OSError as e:
            return handler._err(500, "删除失败: %s" % e)

    if path == "/api/library/reveal":
        # 只允许本机
        client = handler.client_address[0] if handler.client_address else ""
        if client not in ("127.0.0.1", "::1", "localhost"):
            return handler._err(403, "只能在运行服务的这台电脑上打开文件夹")
        rel = (query.get("path") or [""])[0]
        try:
            opened = reveal(rel)
        except (LibUnsafe, OSError) as e:
            return handler._err(400, str(e))
        return handler._json({"ok": True, "opened": opened})

    if path == "/api/library/apps":
        rel = (query.get("path") or [""])[0]
        ext = ""
        if rel:
            try:
                ext = safe_rel(rel).suffix.lower()
            except LibUnsafe:
                ext = ""
        return handler._json({"apps": available_apps(ext), "ext": ext})

    if path == "/api/library/open":
        client = handler.client_address[0] if handler.client_address else ""
        if client not in ("127.0.0.1", "::1", "localhost"):
            return handler._err(403, "「以……打开」只能在运行服务的这台电脑上使用")
        rel = (query.get("path") or [""])[0]
        app_id = (query.get("app") or ["default"])[0]
        try:
            return handler._json(open_with(rel, app_id))
        except (LibUnsafe, FileNotFoundError, ValueError) as e:
            return handler._err(400, str(e))
        except OSError as e:
            return handler._err(500, "系统调用失败: %s" % e)

    return handler._err(404, "未知的 library 路由: %s" % path)
