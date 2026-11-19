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
import shutil
import signal
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from . import languages, pylibs


ENABLED = False
ROOT = None
WEBAPP = Path(__file__).resolve().parent.parent
CONFIG_FILE = WEBAPP / "data" / "ide-config.json"

DEFAULT = {
    "workspace": "练习区",   # 相对资料根
    "defaultDir": "",        # 工作区内的默认保存子目录（空 = 工作区根）
    "python": "",            # 空 = 用当前解释器
    "timeout": 10,           # 秒
    "extraPaths": [],        # 额外的 import 搜索路径（自己的库放这儿）
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
    # 额外的 import 路径：自己的库放这儿，运行前注入 PYTHONPATH / NODE_PATH
    raw_paths = cfg.get("extraPaths")
    if isinstance(raw_paths, str):
        raw_paths = [x for x in raw_paths.replace(";", "\n").splitlines() if x.strip()]
    elif not isinstance(raw_paths, list):
        raw_paths = []
    shown = []
    for item in raw_paths:
        text = str(item or "").strip().strip('"')
        if text:
            shown.append(text)
    cfg["extraPaths"] = shown[:20]
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
    pkgs, pkg_errors = _languages()
    libs_view = pylibs.list_libs(WEBAPP)
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
        # 语言包：哪些能跑、缺什么依赖、支持哪些扩展名
        "languages": languages.describe(pkgs, python_exe()),
        "languageErrors": pkg_errors,
        "extraPaths": cfg.get("extraPaths", []),
        # 私有 Python 库（装到这里，不碰系统环境）
        "pylibs": {
            "dir": str(pylibs.libs_dir(WEBAPP)),
            "count": libs_view["count"],
            "bytes": libs_view["bytes"],
        },
    }


def _languages():
    """扫描语言包（每次现扫：放一个目录就生效，不用重启）。"""
    return languages.scan(WEBAPP)


# ---------------------------------------------------------------------
# 语言包安装 / 卸载（人和 agent 共用同一个入口）
# ---------------------------------------------------------------------
LANG_FIELDS = ("id", "name", "kind", "schema", "ext", "editor",
               "requires", "build", "run", "env", "timeout")


def languages_view():
    pkgs, errors = _languages()
    return {
        "languages": languages.describe(pkgs, python_exe()),
        "languageErrors": errors,
        "pluginsDir": str(languages.plugins_dir(WEBAPP)),
    }


def install_language(data):
    """写入一个语言包：只收声明（JSON），落到 plugins/<id>/plugin.json。

    故意不执行任何插件代码——见 languages.py 顶部说明。
    重复安装同 id = 覆盖（用户自己装的，没有"只读"一说）。
    """
    raw = data if isinstance(data, dict) else {}
    # 允许前端把整个 plugin.json 直接丢进来
    payload = {k: raw.get(k) for k in LANG_FIELDS if raw.get(k) is not None}
    payload["kind"] = "language"
    payload.setdefault("schema", 1)
    lang, why = languages._normalize(payload, "user")
    if not lang:
        raise UnsafeIDE("语言包不合法：%s" % why)

    target = languages.plugins_dir(WEBAPP) / lang["id"]
    manifest = target / "plugin.json"
    target.mkdir(parents=True, exist_ok=True)
    tmp = manifest.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, manifest)
    view = languages_view()
    view.update({"ok": True, "installed": lang["id"]})
    return view


def remove_language(lang_id):
    lang_id = str(lang_id or "").strip().lower()
    if not lang_id or not all(c.isalnum() or c in "-_" for c in lang_id):
        raise UnsafeIDE("语言包 id 非法")
    target = languages.plugins_dir(WEBAPP) / lang_id
    if not target.is_dir():
        raise UnsafeIDE("没有这个语言包：%s" % lang_id)
    shutil.rmtree(str(target))
    view = languages_view()
    view.update({"ok": True, "removed": lang_id})
    return view


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


def _run_step(cmd, cwd, env, timeout):
    """跑一条命令，返回 (退出码, stdout, stderr, 是否超时, 毫秒)。"""
    kwargs = dict(cwd=str(cwd), stdin=subprocess.DEVNULL,
                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000200        # CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    t0 = time.time()
    proc = subprocess.Popen(cmd, **kwargs)
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
    return (proc.returncode,
            out.decode("utf-8", "replace"),
            err.decode("utf-8", "replace"),
            timed_out, ms)


def _env_for(lang, cfg):
    """环境变量：语言包自带 + 自己的库路径。

    多语言不共用同一个检索路径：Python 认 PYTHONPATH、Node 认 NODE_PATH，
    其余语言暂时不注入（避免给出"看起来支持"的错觉）。
    """
    env = os.environ.copy()
    for key, val in (lang.get("env") or {}).items():
        env[str(key)] = str(val)
    extra = [str(p) for p in (cfg.get("extraPaths") or []) if str(p).strip()]
    # 私有库目录恒定前置：agent/用户装到这里的包，运行就能 import 到
    libs = pylibs.libs_dir(WEBAPP)
    if libs.is_dir():
        extra.insert(0, str(libs))
    if extra:
        target = {"python": "PYTHONPATH", "node": "NODE_PATH"}.get(lang["id"])
        if target:
            old = env.get(target) or ""
            env[target] = os.pathsep.join(extra + ([old] if old else []))
    return env


def run_file(rel):
    p = resolve_in(ROOT, rel)
    if not p.is_file():
        raise UnsafeIDE("文件不存在: %s" % rel)

    cfg = load_config()
    pkgs, _errors = _languages()
    lang = languages.find_for(p, pkgs)
    if not lang:
        exts = sorted({e for item in pkgs for e in item["ext"]})
        raise UnsafeIDE("没有语言包认领 %s。当前支持：%s"
                        % (p.suffix or "（无扩展名）", " ".join(exts) or "无"))

    py = python_exe()
    missing = languages.probe(lang, py)
    if missing:
        return {"ok": False, "lang": lang["id"], "langName": lang["name"],
                "error": "「%s」需要 %s，但这台机器上找不到；装好再试。"
                         % (lang["name"], "、".join(missing))}

    timeout = min(cfg["timeout"], int(lang.get("timeout") or cfg["timeout"]))
    exe = languages.exe_path_for(p)
    steps = languages.resolve(lang, p, py, exe)
    env = _env_for(lang, cfg)
    cwd = p.parent

    result = {
        "ok": True,
        "lang": lang["id"],
        "langName": lang["name"],
        "path": str(p.relative_to(ROOT)).replace("\\", "/"),
        "timeout": timeout,
    }

    # 两段式语言（C/C++/Rust…）：先编译，编译失败就没有运行的份
    if steps.get("build"):
        try:
            code, out, err, to, ms = _run_step(steps["build"], cwd, env, timeout)
        except FileNotFoundError:
            return {"ok": False, "lang": lang["id"], "error": "找不到编译器：%s" % steps["build"][0]}
        except OSError as exc:
            return {"ok": False, "lang": lang["id"], "error": "编译启动失败：%s" % exc}
        b_out, b_t1 = _clip(out)
        b_err, b_t2 = _clip(err)
        result["build"] = {
            "cmd": " ".join(steps["build"]), "code": code, "ms": ms,
            "stdout": b_out, "stderr": b_err, "timedOut": to,
        }
        if code != 0 or to:
            result.update({
                "ok": False, "code": code, "stdout": b_out, "stderr": b_err,
                "ms": ms, "timedOut": to, "truncated": b_t1 or b_t2,
                "error": "编译失败（退出码 %s）" % code,
            })
            return result

    try:
        code, out, err, to, ms = _run_step(steps["run"], cwd, env, timeout)
    except FileNotFoundError:
        return {"ok": False, "lang": lang["id"], "error": "找不到运行命令：%s" % steps["run"][0]}
    except OSError as exc:
        return {"ok": False, "lang": lang["id"], "error": "启动失败：%s" % exc}

    stdout, t1 = _clip(out)
    stderr, t2 = _clip(err)
    result.update({
        "code": code, "stdout": stdout, "stderr": stderr,
        "ms": ms, "timedOut": to, "truncated": t1 or t2,
    })
    return result


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
        if "extraPaths" in data:
            cfg["extraPaths"] = data.get("extraPaths")
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

    if path == "/api/ide/languages":
        if getattr(handler, "command", "GET").upper() == "GET":
            return handler._json(languages_view())
        try:
            return handler._json(install_language(_body(handler)))
        except UnsafeIDE as e:
            return handler._err(400, str(e))
        except OSError as e:
            return handler._err(500, "写入语言包失败：%s" % e)

    if path == "/api/ide/languages/remove":
        data = _body(handler)
        try:
            return handler._json(remove_language(data.get("id")))
        except UnsafeIDE as e:
            return handler._err(400, str(e))
        except OSError as e:
            return handler._err(500, "删除语言包失败：%s" % e)

    if path == "/api/ide/pylibs":
        if getattr(handler, "command", "GET").upper() == "GET":
            view = pylibs.describe(WEBAPP, python_exe())
            view["ok"] = True
            return handler._json(view)
        data = _body(handler)
        try:
            res = pylibs.install_planned(WEBAPP, python_exe(), data.get("packages"))
        except ValueError as e:
            return handler._err(400, str(e))
        return handler._json(res)

    if path == "/api/ide/pylibs/clear":
        return handler._json(pylibs.clear(WEBAPP))

    return handler._err(404, "未知 IDE 接口: %s" % path)
