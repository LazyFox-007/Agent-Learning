# -*- coding: utf-8 -*-
"""练习区的私有 Python 库目录。

为什么**不**直接 `pip install` 到当前解释器：

- 那是用户的系统 Python（`...\\Python311\\python.exe`），别的项目也在用；
- 装包可能降级/覆盖已有依赖，而且没有任何"一键还原"；
- 一旦装出问题，影响面超出这个平台。

所以：装到 `_webapp/data/pylibs`（`pip --target`），运行时把这个目录
**前置**进 `PYTHONPATH`。删掉目录 = 完整回滚，系统环境一个字节都没动。

已知限制（写在这里，别假装没有）：
- `--target` 不做包之间的冲突仲裁，同一依赖的不同版本会共存、谁先被找到谁生效
  （前置顺序固定，所以行为是确定的，但不是"自动解决冲突"）；
- 带原生扩展的 wheel 要求本机解释器和 wheel 的 ABI 匹配（同版本 Python 一般没问题）；
- 不用虚拟环境是有意的：venv 要管理创建/失效/重建，收益不如"一个可删目录"直接。
"""

import json
import re
import subprocess
import sys
from pathlib import Path

LIBS_DIRNAME = "pylibs"
INSTALL_TIMEOUT = 180
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
# 这些不是"包名"，但用户会想升级 pip 本身；明确拒绝，避免把 pip 装进 libs 目录
FORBIDDEN = {"pip", "setuptools", "wheel"}


def libs_dir(webapp):
    return Path(webapp) / "data" / LIBS_DIRNAME


def _dist_infos(target):
    if not target.is_dir():
        return []
    return sorted(target.glob("*.dist-info"))


def list_libs(webapp):
    """列出装在私有目录里的包（读 dist-info/METADATA，不启动子进程）。"""
    target = libs_dir(webapp)
    items = []
    for info in _dist_infos(target):
        name = version = None
        try:
            meta = (info / "METADATA").read_text(encoding="utf-8", errors="replace")
            for line in meta.splitlines():
                if not line.strip():
                    break
                if line.startswith("Name: ") and not name:
                    name = line[6:].strip()
                elif line.startswith("Version: ") and not version:
                    version = line[9:].strip()
        except Exception:
            pass
        if not name:
            name = info.name[:-len(".dist-info")]
        items.append({"name": name, "version": version or "?", "dir": info.name})
    return {
        "dir": str(target),
        "exists": target.is_dir(),
        "count": len(items),
        "bytes": dir_size(target),
        "packages": items,
    }


def dir_size(root):
    """目录总字节数（算不准也无所谓，只用来给用户一个量级）。"""
    root = Path(root)
    if not root.is_dir():
        return 0
    total = 0
    for item in root.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def system_versions(python_exe, packages, timeout=20):
    """问解释器：这些包在**系统环境**里有没有、什么版本。

    一次性批量问（起一个子进程），比每个包起一次快得多。
    返回 {包名小写: 版本} —— 不在里面的就是系统没有。
    """
    bare = []
    for item in packages:
        name = re.split(r"[=<>!~\[]", str(item or "").strip(), 1)[0].strip()
        if name and name not in bare:
            bare.append(name)
    if not bare:
        return {}
    script = (
        "import json,sys\n"
        "import importlib.metadata as m\n"
        "out={}\n"
        "for n in json.loads(sys.argv[1]):\n"
        "    try:\n"
        "        out[n]=m.version(n)\n"
        "    except Exception:\n"
        "        pass\n"
        "print(json.dumps(out))\n"
    )
    try:
        proc = subprocess.run(
            [python_exe, "-c", script, json.dumps(bare)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
    except Exception:
        return {}
    if proc.returncode != 0:
        return {}
    try:
        return json.loads(proc.stdout.decode("utf-8", "replace") or "{}")
    except Exception:
        return {}



def normalize_names(raw):
    """把用户输入洗成安全的包名列表；非法直接抛 ValueError。"""
    if isinstance(raw, str):
        parts = re.split(r"[\s,;，；]+", raw)
    elif isinstance(raw, list):
        parts = []
        for item in raw:
            parts.extend(str(item or "").split())
    else:
        parts = []
    names = []
    for part in parts:
        text = str(part or "").strip()
        if not text:
            continue
        # 允许 name==version / name>=1.2 这类常见写法，但只取包名做校验
        bare = re.split(r"[=<>!~\[]", text, 1)[0].strip()
        if not NAME_RE.match(bare):
            raise ValueError("包名不合法：%s" % text)
        if bare.lower() in FORBIDDEN:
            raise ValueError("不往练习区目录里装 %s（请用系统 pip 升级它）" % bare)
        names.append(text)
    if not names:
        raise ValueError("没有给出包名")
    if len(names) > 20:
        raise ValueError("一次最多装 20 个包")
    return names


def install(webapp, python_exe, packages, timeout=INSTALL_TIMEOUT):
    """装到私有目录。返回 (ok, stdout, stderr, 用时秒)。

    注意：这里用列表参数调用（不经 shell），包名虽然洗过，但也不给注入留口子。
    """
    target = libs_dir(webapp)
    target.mkdir(parents=True, exist_ok=True)
    cmd = [
        python_exe, "-m", "pip", "install",
        "--target", str(target),
        "--no-input",
        "--disable-pip-version-check",
        "--no-warn-script-location",
        # 国内环境常见：超时就重试少一点，别让用户等 10 分钟
        "--retries", "1",
        "--timeout", "30",
    ] + list(packages)

    import time
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except FileNotFoundError:
        return False, "", "找不到解释器：%s" % python_exe, 0.0
    except subprocess.TimeoutExpired:
        return False, "", "安装超时（%d 秒）。可能是网络慢或包很大。" % timeout, time.time() - t0
    elapsed = time.time() - t0
    out = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace")
    return proc.returncode == 0, out, err, elapsed


def install_planned(webapp, python_exe, packages, timeout=INSTALL_TIMEOUT):
    """先探测系统环境和私有目录，只把真正"缺的"装进去。返回结构化结果。"""
    names = normalize_names(packages)
    decision = plan(python_exe, names)

    # 私有目录里已经有的也不算"缺"（否则 pip 每次都会警告 target 已存在）
    have_local = {p["name"].lower() for p in list_libs(webapp)["packages"]}
    still_need = []
    for item in decision["need"]:
        bare = re.split(r"[=<>!~\[]", str(item).strip(), 1)[0].strip().lower()
        if bare in have_local:
            decision["skipped"].append(bare)
        else:
            still_need.append(item)
    decision["need"] = still_need

    if not decision["need"]:
        view = list_libs(webapp)
        skipped = decision["skipped"]
        return {
            "ok": True, "installed": [], "skipped": skipped,
            "log": "没有需要新装的包（系统环境或私有目录里已经有：%s）" % ", ".join(skipped),
            **view,
        }
    ok, out, err, secs = install(webapp, python_exe, decision["need"], timeout)
    view = list_libs(webapp)
    return {
        "ok": ok,
        "installed": decision["need"] if ok else [],
        "skipped": decision["skipped"],
        "seconds": round(secs, 1),
        "log": (out + err)[-8000:],
        "error": None if ok else (err or out)[-2000:] or "pip 返回失败",
        **view,
    }


def clear(webapp):
    """清空私有库目录（不动系统环境）。"""
    target = libs_dir(webapp)
    removed = 0
    if target.is_dir():
        import shutil
        for item in list(target.iterdir()):
            try:
                if item.is_dir() and not item.is_symlink():
                    shutil.rmtree(str(item))
                else:
                    item.unlink()
                removed += 1
            except OSError:
                continue
    view = list_libs(webapp)
    view.update({"ok": True, "removed": removed})
    return view


def describe(webapp, python_exe=""):
    """给前端/agent 的视图：私有目录内容 + 系统里同名的包（避免重复装）。"""
    view = list_libs(webapp)
    view["python"] = python_exe or sys.executable
    if python_exe:
        names = [p["name"] for p in view["packages"]]
        view["system"] = system_versions(python_exe, names) if names else {}
    return view


def plan(python_exe, packages):
    """先问系统，再决定装什么。

    返回 {"have": {名: 版本}, "need": [原始写法...], "skipped": [名...]}。
    这就是"不重复装"的核心：系统里已经有的，一律不再进私有目录。
    """
    have = system_versions(python_exe, packages)
    need, skipped = [], []
    for item in packages:
        name = re.split(r"[=<>!~\[]", str(item or "").strip(), 1)[0].strip()
        if name and name.lower() in {k.lower() for k in have}:
            skipped.append(name)
        else:
            need.append(item)
    return {"have": have, "need": need, "skipped": skipped}



def json_summary(webapp):
    return json.dumps(list_libs(webapp), ensure_ascii=False)
