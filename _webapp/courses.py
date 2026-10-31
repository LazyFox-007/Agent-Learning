#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""课程包 —— 严格的格式约束

为什么要这套东西
  书库允许用户丢进来任何格式的文件，但「课程」是会被当作正式教材展示的，
  必须有统一的外壳，否则目录树、进度、搜索都会各说各话。

一句话规则
  有合法的 course.json 才是课程；没有 → 只能当书库资料。

课程包结构
  课程名/
  ├── course.json      必需，元数据（下面有字段说明）
  ├── index.html       入口（由 course.json 的 entry 指定）
  └── ...              章节、图片、代码，内容怎么组织不限

course.json 字段
  必需  id        小写字母开头，只含小写字母/数字/连字符，3~32 字符
        title     1~60 字
        version   语义化版本，如 1.0.0
        entry     课程目录内的 .html 或 .md 文件，必须真实存在
  可选  description / author / license / tags / order

校验规则（任一不过即拒绝）
  1. course.json 存在、合法 JSON、是对象
  2. 必需字段齐全且类型正确
  3. id 格式合法且在全部课程里唯一
  4. entry 在课程目录内、扩展名是 .html/.md、文件真实存在
  5. 全包文件扩展名都在白名单里
  6. 单文件 <= 20MB，整包 <= 300MB
  7. 课程目录不能是书库，也不能和书库互相嵌套
"""

import json
import os
import re
from pathlib import Path

# 内容文件：会被渲染给读者看的，白名单严格
COURSE_EXT = {
    ".md", ".markdown", ".html", ".htm", ".txt",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico",
    ".py", ".js", ".css", ".json", ".ipynb",
    ".pdf", ".pptx", ".docx",
}

# 包文件：不会被渲染，只是随包附带（许可证、构建脚本、配置）。
# 允许，但会在 warnings 里提示 —— 应用本身从不执行它们。
PKG_EXT = {".ps1", ".sh", ".bat", ".cmd", ".toml", ".yml", ".yaml", ".ini", ".cfg"}

# 无扩展名但属于标准包文件的名字
PKG_NAMES = {
    "license", "license.txt", "notice", "readme", "changelog",
    "copying", "authors", "contributors", "makefile", "dockerfile",
    ".gitignore", ".gitattributes", ".editorconfig",
}

MAX_FILE_SIZE = 20 * 1024 * 1024        # 单文件 20 MB
MAX_PKG_SIZE = 300 * 1024 * 1024        # 整包 300 MB
MAX_FILES = 5000

ID_RE = re.compile(r"^[a-z][a-z0-9-]{2,31}$")
VER_RE = re.compile(r"^\d+\.\d+\.\d+([\-+][0-9A-Za-z.\-]+)?$")

_root = None
_lib_dirname = "书库"


def configure(root, lib_dirname="书库"):
    global _root, _lib_dirname
    _root = Path(root).resolve()
    _lib_dirname = lib_dirname or "书库"


# ---------------------------------------------------------------
# 单个课程包的校验
# ---------------------------------------------------------------
def validate_pkg(pkg_dir):
    """校验一个课程包目录。

    返回 {ok, dir, id, title, entry, errors[], warnings[], stats}
    不抛异常 —— 校验失败是常态，用 errors 表达。
    """
    pkg = Path(pkg_dir).resolve()
    res = {
        "ok": False, "dir": str(pkg), "name": pkg.name,
        "id": None, "title": None, "entry": None,
        "errors": [], "warnings": [],
        "files": 0, "bytes": 0, "kinds": {},
    }

    # 1. course.json
    cfg_path = pkg / "course.json"
    if not cfg_path.is_file():
        res["errors"].append("缺少 course.json")
        return res

    try:
        meta = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    except Exception as e:
        res["errors"].append("course.json 解析失败: %s" % e)
        return res
    if not isinstance(meta, dict):
        res["errors"].append("course.json 必须是一个对象")
        return res

    # 2. 必需字段
    cid = meta.get("id")
    if not isinstance(cid, str) or not ID_RE.match(cid):
        res["errors"].append("id 不合法（小写字母开头，3~32 位，只含小写字母/数字/连字符）")
    else:
        res["id"] = cid

    title = meta.get("title")
    if not isinstance(title, str) or not (1 <= len(title.strip()) <= 60):
        res["errors"].append("title 不合法（1~60 字）")
    else:
        res["title"] = title.strip()

    ver = meta.get("version")
    if not isinstance(ver, str) or not VER_RE.match(ver):
        res["errors"].append("version 不合法（应为 1.0.0 这种语义化版本）")
    else:
        res["version"] = ver

    entry = meta.get("entry")
    if not isinstance(entry, str) or not entry.strip():
        res["errors"].append("缺少 entry")
    else:
        entry = entry.strip().replace("\\", "/")
        if entry.startswith("/") or ".." in entry.split("/"):
            res["errors"].append("entry 必须指向课程目录内部")
        else:
            ext = os.path.splitext(entry)[1].lower()
            if ext not in (".html", ".htm", ".md", ".markdown"):
                res["errors"].append("entry 只能是 .html 或 .md")
            elif not (pkg / entry).is_file():
                res["errors"].append("entry 指向的文件不存在: %s" % entry)
            else:
                res["entry"] = entry

    for opt in ("description", "author", "license"):
        if opt in meta and not isinstance(meta[opt], str):
            res["warnings"].append("%s 应该是字符串，已忽略" % opt)

    # 3. 遍历整包
    total = 0
    count = 0
    kinds = {}
    bad_ext = []
    pkg_files = []
    too_big = []

    for dirpath, dirnames, filenames in os.walk(pkg):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]
        for fn in filenames:
            if fn.startswith("."):
                continue
            fp = Path(dirpath) / fn
            try:
                size = fp.stat().st_size
            except OSError:
                continue
            count += 1
            total += size
            ext = fp.suffix.lower()
            relname = str(fp.relative_to(pkg)).replace("\\", "/")
            kinds[ext or "(无扩展名)"] = kinds.get(ext or "(无扩展名)", 0) + 1

            if ext in COURSE_EXT:
                pass                                   # 内容文件，正常
            elif ext in PKG_EXT or fn.lower() in PKG_NAMES:
                if len(pkg_files) < 12:
                    pkg_files.append(relname)          # 包文件，允许但要提示
            else:
                if len(bad_ext) < 8:
                    bad_ext.append(relname)
            if size > MAX_FILE_SIZE:
                if len(too_big) < 8:
                    too_big.append("%s (%.1f MB)" % (
                        str(fp.relative_to(pkg)).replace("\\", "/"), size / 1048576))

    res["files"] = count
    res["bytes"] = total
    res["kinds"] = dict(sorted(kinds.items(), key=lambda x: -x[1])[:10])

    if count > MAX_FILES:
        res["errors"].append("文件数 %d 超过上限 %d" % (count, MAX_FILES))
    if total > MAX_PKG_SIZE:
        res["errors"].append("整包 %.1f MB 超过上限 %.0f MB" % (total / 1048576, MAX_PKG_SIZE / 1048576))
    if pkg_files:
        res["warnings"].append("附带 %d 个非内容文件（不会被渲染）: %s" % (
            len(pkg_files), ", ".join(pkg_files)))
    if bad_ext:
        res["errors"].append("存在不允许的文件类型: %s" % ", ".join(bad_ext))
    if too_big:
        res["errors"].append("存在超大文件: %s" % ", ".join(too_big))

    res["ok"] = not res["errors"]
    return res


# ---------------------------------------------------------------
# 扫描全部课程包
# ---------------------------------------------------------------
def scan_courses():
    """扫描资料根目录下所有带 course.json 的目录并校验。

    只扫一层（课程必须直接放在根目录），书库永远不参与。
    """
    out = []
    if _root is None:
        return out

    try:
        entries = list(os.scandir(_root))
    except OSError:
        return out

    seen_ids = {}
    for e in entries:
        if not e.is_dir(follow_symlinks=False):
            continue
        name = e.name
        if name.startswith(".") or name == _lib_dirname:
            continue
        pkg = Path(e.path)
        if not (pkg / "course.json").is_file():
            continue
        r = validate_pkg(pkg)
        # id 唯一性
        if r.get("id"):
            if r["id"] in seen_ids:
                r["errors"].append("id 与其他课程重复: %s" % r["id"])
                r["ok"] = False
            else:
                seen_ids[r["id"]] = name
        out.append(r)

    out.sort(key=lambda x: (not x["ok"], x.get("title") or x["name"]))
    return out


def list_ok():
    return [c for c in scan_courses() if c["ok"]]


# ---------------------------------------------------------------
# 路由
# ---------------------------------------------------------------
def handle(handler, path, query):
    if path == "/api/courses":
        all_ = scan_courses()
        return handler._json({
            "courses": [c for c in all_ if c["ok"]],
            "rejected": [c for c in all_ if not c["ok"]],
            "spec": {
                "required": ["id", "title", "version", "entry"],
                "entryExt": [".html", ".md"],
                "allowedExt": sorted(COURSE_EXT),
                "maxFileMB": MAX_FILE_SIZE // 1048576,
                "maxPkgMB": MAX_PKG_SIZE // 1048576,
            },
        })

    if path == "/api/courses/validate":
        rel = (query.get("dir") or [""])[0]
        if not rel:
            return handler._json({"courses": scan_courses()})
        try:
            p = (_root / rel).resolve()
            p.relative_to(_root)
        except (ValueError, OSError):
            return handler._err(403, "路径越界")
        if not p.is_dir():
            return handler._err(404, "目录不存在")
        return handler._json(validate_pkg(p))

    return handler._err(404, "未知的 courses 路由: %s" % path)
