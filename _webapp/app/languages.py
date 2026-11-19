# -*- coding: utf-8 -*-
"""语言包：把「哪种文件用哪个命令跑」从代码里挪到数据里。

一个语言包 = `_webapp/plugins/<id>/plugin.json`，**只有声明，没有脚本**。
这样做的好处：
- 加一门语言 = 放一个目录，删目录即卸载；
- 插件里没有可执行代码，不会给 `--ide` 再开一个"任意代码执行"的口子；
- 全部字段有兜底，坏插件只会被跳过并在设置里报出来，不会拖垮服务。

字段（除 run 外都可省）：

    id        必填，小写 slug
    name      显示名
    ext       必填，扩展名数组，如 [".cpp"]
    editor    Monaco 的 language id，默认取 id
    requires  运行依赖的命令名，如 ["g++"]；没装就不显示这门语言
    build     可选，两段式语言的编译步骤 {cmd, args}
    run       必填，{cmd, args}
    env       额外环境变量
    timeout   秒，1..120，默认 10

占位符：{file} 绝对路径 · {dir} 所在目录 · {stem} 文件名（无扩展名）
        {python} 配置的解释器 · {exe} 本次构建产出的可执行文件路径
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

PLACEHOLDERS = ("{file}", "{dir}", "{stem}", "{python}", "{exe}")

# 兜底：plugins 目录为空（或全坏）时至少还能跑 Python
BUILTIN = [
    {
        "id": "python",
        "name": "Python",
        "ext": [".py"],
        "editor": "python",
        "requires": ["{python}"],
        "run": {"cmd": "{python}", "args": ["-u", "{file}"]},
        "env": {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
        "timeout": 10,
    }
]


def plugins_dir(webapp):
    return Path(webapp) / "plugins"


def _clean_list(value):
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _clean_step(step):
    """{cmd, args} → 已清洗的步骤；不合法返回 None。"""
    if not isinstance(step, dict):
        return None
    cmd = str(step.get("cmd") or "").strip()
    if not cmd:
        return None
    args = [str(a) for a in (step.get("args") or [])]
    return {"cmd": cmd, "args": args}


def _normalize(raw, source):
    """把一份 plugin.json 洗成内部结构；不合法返回 (None, 原因)。"""
    if not isinstance(raw, dict):
        return None, "不是对象"
    lang_id = str(raw.get("id") or "").strip().lower()
    if not lang_id or not all(c.isalnum() or c in "-_" for c in lang_id):
        return None, "id 非法（只能小写字母/数字/-/_）"
    ext = [e if e.startswith(".") else "." + e for e in _clean_list(raw.get("ext"))]
    if not ext:
        return None, "缺少 ext"
    run = _clean_step(raw.get("run"))
    if not run:
        return None, "缺少 run.cmd"
    build = _clean_step(raw.get("build"))
    if raw.get("build") is not None and not build:
        return None, "build 不合法（需要 cmd）"
    try:
        timeout = int(raw.get("timeout") or 10)
    except (TypeError, ValueError):
        timeout = 10
    env = raw.get("env")
    if not isinstance(env, dict):
        env = {}
    return {
        "id": lang_id,
        "name": str(raw.get("name") or lang_id),
        "ext": ext,
        "editor": str(raw.get("editor") or lang_id),
        "requires": _clean_list(raw.get("requires")) or [run["cmd"]],
        "build": build,
        "run": run,
        "env": {str(k): str(v) for k, v in env.items()},
        "timeout": max(1, min(120, timeout)),
        "source": source,
    }, None


def scan(webapp):
    """扫描语言包。返回 (languages, errors)。

    plugins 里的同 id 覆盖内置；扫描失败不会清空内置，保证总能跑 Python。
    """
    langs = {}
    errors = []
    for item in BUILTIN:
        lang, why = _normalize(item, "builtin")
        if lang:
            langs[lang["id"]] = lang
        elif why:
            errors.append("builtin: %s" % why)

    root = plugins_dir(webapp)
    if root.is_dir():
        for sub in sorted(root.iterdir()):
            if not sub.is_dir() or sub.name.startswith((".", "_")):
                continue
            manifest = sub / "plugin.json"
            if not manifest.is_file():
                continue
            try:
                raw = json.loads(manifest.read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append("%s: plugin.json 读不出来（%s）" % (sub.name, exc))
                continue
            if isinstance(raw, dict) and str(raw.get("kind") or "language") != "language":
                continue
            lang, why = _normalize(raw, sub.name)
            if lang:
                langs[lang["id"]] = lang
            else:
                errors.append("%s: %s" % (sub.name, why))

    ordered = sorted(langs.values(), key=lambda x: (x["id"] != "python", x["id"]))
    return ordered, errors


def which_python(configured):
    """`{python}` 占位符解析：配置的解释器，空则当前解释器。"""
    return str(configured or "").strip() or sys.executable


def probe(lang, python_exe):
    """这门语言现在能不能用：返回缺失的依赖列表（空 = 可用）。"""
    missing = []
    for need in lang["requires"]:
        if need == "{python}":
            if not Path(python_exe).exists() and not shutil.which(python_exe):
                missing.append(python_exe)
            continue
        if not shutil.which(need):
            missing.append(need)
    return missing


def describe(languages, python_exe):
    """给前端/状态接口用的精简视图。"""
    out = []
    for lang in languages:
        missing = probe(lang, python_exe)
        out.append({
            "id": lang["id"],
            "name": lang["name"],
            "ext": lang["ext"],
            "editor": lang["editor"],
            "requires": lang["requires"],
            "available": not missing,
            "missing": missing,
            "twoStage": bool(lang["build"]),
            "timeout": lang["timeout"],
            "source": lang["source"],
        })
    return out


def find_for(path, languages):
    """按扩展名找语言；找不到返回 None。"""
    suffix = Path(path).suffix.lower()
    for lang in languages:
        if suffix in [e.lower() for e in lang["ext"]]:
            return lang
    return None


def _subst(text, values):
    out = str(text)
    for key, val in values.items():
        out = out.replace(key, val)
    return out


def resolve(lang, file_path, python_exe, exe_path):
    """拼出 build / run 的实际命令（占位符已替换）。"""
    file_path = str(Path(file_path))
    values = {
        "{file}": file_path,
        "{dir}": str(Path(file_path).parent),
        "{stem}": Path(file_path).stem,
        "{python}": python_exe,
        "{exe}": exe_path,
    }

    def step(raw):
        if not raw:
            return None
        return [_subst(raw["cmd"], values)] + [_subst(a, values) for a in raw["args"]]

    return {"build": step(lang["build"]), "run": step(lang["run"])}


def exe_path_for(file_path):
    """构建产物放临时目录，不污染练习区。"""
    base = Path(tempfile.mkdtemp(prefix="ide-run-"))
    stem = Path(file_path).stem or "a"
    return str(base / (stem + (".exe" if os.name == "nt" else "")))
