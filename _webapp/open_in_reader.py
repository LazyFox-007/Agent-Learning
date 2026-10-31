#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Windows 资源管理器右键调用：用大肥鱼阅读器打开这个文件。

调用方式（由注册表里的右键菜单触发）
    pythonw.exe open_in_reader.py "D:\\书\\三体.md"

流程
    1. 在 8777~8796 里找已经跑着的服务；找不到就自己拉起来
    2. 文件在资料根目录内   → 直接用相对路径打开
       文件在资料根目录外   → 复制一份到 书库/导入/ 再打开
    3. 用默认浏览器打开对应地址

为什么用 pythonw
    从资源管理器调用时不应该闪出一个黑框，所以注册表里挂 pythonw.exe。
    代价是没有 stdout，出错只能写日志 —— 所以下面所有异常都会落盘。
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

WEBAPP = Path(__file__).resolve().parent
ROOT = WEBAPP.parent
LIB_DIRNAME = "书库"
IMPORT_SUBDIR = "导入"
PREVIEW_DIR = ".preview"          # 临时预览区，藏起来不进列表
LOG = WEBAPP / "_logs" / "open-with.log"

PORT_START, PORT_TRIES = 8777, 20


def log(msg):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def ping(port, timeout=0.35):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/ping" % port,
                                    timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
            return data if data.get("ok") else None
    except (urllib.error.URLError, OSError, ValueError):
        return None


def find_server():
    for port in range(PORT_START, PORT_START + PORT_TRIES):
        d = ping(port)
        if d:
            return port, Path(d.get("root") or ROOT)
    return None, None


def start_server():
    """后台拉起服务，等到能吃 ping 为止。"""
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        exe = exe[:-11] + "python.exe"          # 服务本身要有控制台，便于查看日志
    if not Path(exe).exists():
        exe = "python"

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    subprocess.Popen(
        [exe, "server.py", "--no-browser", "--auto-exit"],
        cwd=str(WEBAPP),
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )

    for _ in range(60):                          # 最多等 15 秒
        time.sleep(0.25)
        port, root = find_server()
        if port:
            return port, root
    return None, None


def ask_import(src):
    """问一句要不要导入。返回 True 表示用户同意。

    pythonw 没有控制台，只能用系统对话框。ctypes 调 MessageBoxW 不需要 tkinter。
    """
    name = src.name
    text = (
        "「%s」不在书库目录里。\n\n"
        "要复制一份到  书库\导入\  再用阅读器打开吗？\n\n"
        "选「否」就什么也不做。"
    ) % name
    title = "大肥鱼阅读器"

    if os.name != "nt":
        return False

    try:
        import ctypes
        MB_YESNO = 0x04
        MB_ICONQUESTION = 0x20
        MB_TOPMOST = 0x40000
        MB_DEFBUTTON2 = 0x100          # 默认焦点放在「否」，防手快
        r = ctypes.windll.user32.MessageBoxW(
            None, text, title,
            MB_YESNO | MB_ICONQUESTION | MB_TOPMOST | MB_DEFBUTTON2)
        log("询问导入 %s → %s" % (name, "同意" if r == 6 else "取消"))
        return r == 6                   # 6 = IDYES
    except Exception as e:
        log("弹窗失败: %s" % e)
        return False


def unique_dest(folder, name):
    """同名不覆盖，自动加 (2)(3)…"""
    dest = folder / name
    if not dest.exists():
        return dest
    stem, ext = os.path.splitext(name)
    for i in range(2, 1000):
        cand = folder / ("%s (%d)%s" % (stem, i, ext))
        if not cand.exists():
            return cand
    return folder / ("%s-%d%s" % (stem, int(time.time()), ext))


def rel_inside(path, root):
    """path 是否在 root 内，是则返回相对路径字符串（用 / 分隔）。"""
    try:
        return str(Path(path).resolve().relative_to(root.resolve())).replace("\\", "/")
    except (ValueError, OSError):
        return None


def main():
    if len(sys.argv) < 2:
        log("没有传入文件路径")
        return 1

    raw = sys.argv[1]
    src = Path(raw)
    log("请求打开: %s" % raw)

    if not src.exists():
        log("文件不存在: %s" % raw)
        return 1

    port, root = find_server()
    if not port:
        log("服务没在跑，尝试启动")
        port, root = start_server()
    if not port:
        log("启动失败，放弃")
        return 1
    log("服务端口 %d，资料根 %s" % (port, root))

    # 文件夹：不复制（可能几个 G），只打开对应位置或书库根
    if src.is_dir():
        rel = rel_inside(src, root)
        if rel is None:
            rel = ""                      # 目录在外面 → 回书库根
        url = "http://127.0.0.1:%d/#/%s" % (port, urllib.parse.quote(rel))
        log("打开目录 %s" % url)
        webbrowser.open(url)
        return 0

    rel = rel_inside(src, root)

    if rel is None:
        # 不在资料目录里 —— 先放进隐藏的预览区，直接打开，不打扰。
        # 真正「要不要留下」等到退出时再问（见 server.py 的 _ask_pending_previews）。
        import uuid
        pdir = root / LIB_DIRNAME / PREVIEW_DIR / uuid.uuid4().hex[:12]
        try:
            pdir.mkdir(parents=True, exist_ok=True)
            dest = pdir / src.name
            shutil.copy2(str(src), str(dest))
        except OSError as e:
            log("预览复制失败: %s" % e)
            return 1
        rel = rel_inside(dest, root)
        log("临时预览: %s" % rel)


    url = "http://127.0.0.1:%d/#/%s" % (port, urllib.parse.quote(rel))
    log("打开 %s" % url)
    webbrowser.open(url)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        import traceback
        log("未捕获异常:\n" + traceback.format_exc())
        sys.exit(1)
