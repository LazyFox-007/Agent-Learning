#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""练习区：保存文件 + 运行 Python。

设计原则（和 ai.py 一样，从 server.py 里独立出来）：
- **默认关闭**：只有启动时加 `--ide` 才挂载路由，否则连入口都不给。
- **只写工作区**：保存只允许写进「工作区」目录（默认 练习区/，可配置），
  课程正文永远只读 —— 避免把 git 仓库改脏。
- **可配置**：工作区目录、Python 解释器、超时都写在 .ide-config.json 里，
  和 VSCode 的 settings 一样，改了即时生效。
- **跨平台**：解释器默认用 sys.executable；子进程强制 UTF-8；
  超时按平台杀进程组（Windows taskkill /T，POSIX killpg）。
"""

import json
import os
import signal
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ENABLED = False
ROOT = None
WEBAPP = Path(__file__).resolve().parent.parent
CONFIG_FILE = WEBAPP / "data" / "ide-config.json"

DEFAULT = {
    "workspace": "练习区",   # 相对资料根
    "defaultDir": "",        # 工作区内的默认保存子目录（空 = 工作区根）
    "python": "",            # 空 = 用当前解释器
    "timeout": 10,           # 秒
}

MAX_SAVE = 2 * 1024 * 1024        # 单文件保存上限 2 MB
MAX_OUTPUT = 200 * 1024           # 单个输出流保留上限 200 KB


# ---------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------
def configure(root):
    global ROOT
    ROOT = Path(root).resolve()


def load_config():
    cfg = dict(DEFAULT)
    try:
        if CONFIG_FILE.is_file():
            saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                for k in DEFAULT:
                    if k in saved:
                        cfg[k] = saved[k]
    except Exception:
        pass
    # 清洗
    cfg["workspace"] = str(cfg.get("workspace") or DEFAULT["workspace"]).strip().replace("\\", "/").strip("/")
    if not cfg["workspace"]:
        cfg["workspace"] = DEFAULT["workspace"]
    try:
        cfg["timeout"] = max(1, min(120, int(cfg.get("timeout") or DEFAULT["timeout"])))
    except (TypeError, ValueError):
        cfg["timeout"] = DEFAULT["timeout"]
    cfg["python"] = str(cfg.get("python") or "").strip()
    cfg["defaultDir"] = str(cfg.get("defaultDir") or "").strip().replace("\\", "/").strip("/")
    return cfg


def save_config(cfg):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, CONFIG_FILE)


def _workspace_from(cfg):
    """按给定的配置解析工作区（不读磁盘），越界抛异常。"""
    rel = str(cfg.get("workspace") or DEFAULT["workspace"]).replace("\\", "/").strip("/")
    p = (ROOT / rel).resolve()
    if p != ROOT and ROOT not in p.parents:
        raise UnsafeIDE("工作区必须位于资料根内: %s" % rel)
    return p


def workspace_dir(create=False):
    """工作区绝对路径（必须在资料根内，否则文件读不到）。"""
    p = _workspace_from(load_config())
    if create:
        p.mkdir(parents=True, exist_ok=True)
    return p


def python_exe():
    cfg = load_config()
    return cfg["python"] or sys.executable


def status():
    cfg = load_config()
    try:
        ws = workspace_dir()
        ws_ok = True
        ws_rel = str(ws.relative_to(ROOT)).replace("\\", "/")
    except Exception:
        ws_ok = False
        ws_rel = cfg["workspace"]
        ws = ROOT / cfg["workspace"]
    return {
        "enabled": ENABLED,
        "workspace": ws_rel,
        "workspaceAbs": str(ws),
        "defaultDir": cfg.get("defaultDir", ""),
        "workspaceReady": ws_ok,
        "python": python_exe(),
        "pythonCustom": bool(cfg["python"]),
        "timeout": cfg["timeout"],
        "platform": sys.platform,
    }


# ---------------------------------------------------------------------
# 路径安全
# ---------------------------------------------------------------------
class UnsafeIDE(Exception):
    pass


def _clean_rel(rel):
    rel = urllib.parse.unquote(str(rel or "")).replace("\\", "/").strip()
    if not rel:
        raise UnsafeIDE("路径为空")
    if "\x00" in rel:
        raise UnsafeIDE("路径含 NUL")
    p = Path(rel)
    # Windows 上 Path("/abs.py").is_absolute() 是 False，所以还要单独挡前导斜杠与盘符
    if rel.startswith("/") or rel.startswith("//"):
        raise UnsafeIDE("不接受绝对路径: %s" % rel)
    if p.is_absolute() or p.drive or (len(rel) > 1 and rel[1] == ":"):
        raise UnsafeIDE("不接受绝对路径: %s" % rel)
    parts = [x for x in rel.split("/") if x not in ("", ".")]
    if any(x == ".." for x in parts):
        raise UnsafeIDE("不允许 .. 出界: %s" % rel)
    return "/".join(parts)


def resolve_in(base, rel):
    """把相对路径解析到 base 目录内，越界抛异常。"""
    rel = _clean_rel(rel)
    p = (base / rel).resolve()
    if p != base and base not in p.parents:
        raise UnsafeIDE("越界: %s" % rel)
    return p


# ---------------------------------------------------------------------
# 保存
# ---------------------------------------------------------------------
def save_file(rel, content):
    """rel 是「资料根相对路径」，且必须落在工作区里。"""
    if not isinstance(content, str):
        raise UnsafeIDE("content 必须是字符串")
    data = content.encode("utf-8")
    if len(data) > MAX_SAVE:
        raise UnsafeIDE("内容超过 %.0f MB 上限" % (MAX_SAVE / 1048576))

    ws = workspace_dir(create=True)
    p = resolve_in(ROOT, rel)
    if p != ws and ws not in p.parents:
        raise UnsafeIDE("只能保存到工作区（%s）内，课程文件是只读的"
                        % str(ws.relative_to(ROOT)).replace("\\", "/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, p)
    return {
        "ok": True,
        "path": str(p.relative_to(ROOT)).replace("\\", "/"),
        "name": p.name,
        "bytes": len(data),
    }


# ---------------------------------------------------------------------
# 运行
# ---------------------------------------------------------------------
def _kill_tree(proc):
    """超时后连同子进程一起杀掉（跨平台）。"""
    try:
        if os.name == "nt":
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _clip(text):
    if len(text) <= MAX_OUTPUT:
        return text, False
    return "…（前段已省略）\n" + text[-MAX_OUTPUT:], True


def run_file(rel):
    p = resolve_in(ROOT, rel)
    if not p.is_file():
        raise UnsafeIDE("文件不存在: %s" % rel)
    if p.suffix.lower() != ".py":
        raise UnsafeIDE("目前只支持运行 .py 文件")

    cfg = load_config()
    timeout = cfg["timeout"]
    cmd = [python_exe(), "-u", str(p)]

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"          # Windows 上强制 UTF-8，避免 GBK 乱码
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"

    kwargs = dict(cwd=str(p.parent), stdin=subprocess.DEVNULL,
                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000200        # CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    t0 = time.time()
    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except FileNotFoundError:
        return {"ok": False, "error": "找不到 Python 解释器：%s" % cmd[0]}
    except OSError as e:
        return {"ok": False, "error": "启动失败：%s" % e}

    timed_out = False
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=5)
        except Exception:
            out, err = b"", b""

    ms = int((time.time() - t0) * 1000)
    stdout, t1 = _clip(out.decode("utf-8", "replace"))
    stderr, t2 = _clip(err.decode("utf-8", "replace"))
    return {
        "ok": True,
        "code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "ms": ms,
        "timedOut": timed_out,
        "timeout": timeout,
        "truncated": t1 or t2,
        "path": str(p.relative_to(ROOT)).replace("\\", "/"),
    }


# ---------------------------------------------------------------------
# 路由（由 server.py 调用）
# ---------------------------------------------------------------------
def _body(handler):
    raw = handler._read_body(limit=8 * 1024 * 1024)
    try:
        return json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        raise UnsafeIDE("请求体不是合法 JSON")


def list_workspace():
    """列出工作区里的文件（供 /ide 落地页展示）。"""
    ws = workspace_dir(create=True)
    items = []
    for f in sorted(ws.rglob("*")):
        if not f.is_file() or f.name.endswith(".tmp"):
            continue
        try:
            st = f.stat()
        except OSError:
            continue
        items.append({
            "path": str(f.relative_to(ROOT)).replace("\\", "/"),
            "name": f.relative_to(ws).as_posix(),
            "size": st.st_size,
            "mtime": int(st.st_mtime),
        })
        if len(items) >= 500:
            break
    dirs = [""]
    for d in sorted(ws.rglob("*")):
        if d.is_dir() and d.name not in ("__pycache__",) and not d.name.startswith("."):
            dirs.append(d.relative_to(ws).as_posix())
            if len(dirs) >= 200:
                break
    return {"workspace": str(ws.relative_to(ROOT)).replace("\\", "/"),
            "defaultDir": load_config().get("defaultDir", ""),
            "dirs": dirs, "items": items, "truncated": len(items) >= 500}


def handle(handler, path, query):
    if path == "/api/ide/status":
        return handler._json(status())

    if not ENABLED:
        return handler._err(403, "IDE 未启用（启动时加 --ide）")

    if path == "/api/ide/list":
        try:
            return handler._json(list_workspace())
        except Exception as e:
            return handler._err(500, "读取工作区失败：%s" % e)

    if path == "/api/ide/config":
        data = _body(handler)
        cfg = load_config()
        if "workspace" in data:
            cfg["workspace"] = str(data.get("workspace") or DEFAULT["workspace"])
        if "defaultDir" in data:
            cfg["defaultDir"] = str(data.get("defaultDir") or "").strip().replace("\\", "/").strip("/")
        if "python" in data:
            cfg["python"] = str(data.get("python") or "").strip()
        if "timeout" in data:
            try:
                cfg["timeout"] = max(1, min(120, int(data["timeout"])))
            except (TypeError, ValueError):
                pass
        cfg["workspace"] = cfg["workspace"].strip().replace("\\", "/").strip("/") or DEFAULT["workspace"]
        # 校验的是「即将保存的新配置」，不是磁盘上的旧配置
        try:
            _workspace_from(cfg).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return handler._err(400, "工作区不可用：%s" % e)
        save_config(cfg)
        return handler._json(status())

    if path == "/api/ide/save":
        data = _body(handler)
        try:
            res = save_file(data.get("path"), data.get("content"))
        except UnsafeIDE as e:
            return handler._err(400, str(e))
        except OSError as e:
            return handler._err(500, "写入失败：%s" % e)
        return handler._json(res)

    if path == "/api/ide/run":
        data = _body(handler)
        try:
            res = run_file(data.get("path"))
        except UnsafeIDE as e:
            return handler._err(400, str(e))
        return handler._json(res)

    return handler._err(404, "未知 IDE 接口: %s" % path)
