# _webapp · 实现说明

本地学习平台的**服务端与前端实现**。使用方式、功能清单、课程来源见仓库根目录的
[README.md](../README.md)；这里只写「代码怎么组织、改动去哪找」。

---

## 一、怎么跑

```powershell
cd _webapp
python server.py              # 默认 http://127.0.0.1:8777/
```

- 只绑 `127.0.0.1`；端口被占用会自动顺延（8777→8796）
- 同一资料根**已经在跑时不会再起第二个实例**，直接打开浏览器就退出
- 双击 `start.bat` 等价于上面这条命令

可选参数：

| 参数 | 作用 |
|---|---|
| `--no-browser` | 不自动打开浏览器 |
| `--library` | 启用「我的书库」功能（删除、拖拽排序、右键打开） |
| `--lan` | 绑 `0.0.0.0` 并要求 `?t=` 令牌（给同一 WiFi 的手机用） |
| `--bind <IP>` | 额外绑一块网卡（USB 共享网络）。**不带令牌**，别绑 WiFi 网卡 |
| `--auto-exit[=秒]` | 所有页面关闭后过 N 秒自动退出（默认关） |
| `--force` | 忽略「已在运行」检测，强行再起一个实例 |

---

## 二、代码结构

| 文件 | 职责 |
|---|---|
| `server.py` | HTTP 层：路由、静态文件、目录树、文件读取、搜索、统计、SSE 代理 |
| `app/ai.py` | AI 陪读：服务商预设、密钥存取（只落本机）、系统提示词、演示模式、模型调用、错误翻译 |
| `app/ide.py` | 练习区：保存到工作区、运行 Python（超时强杀 / 输出截断 / 跨平台） |
| `app/courses.py` | 课程包校验：目录结构、入口文件、体积、许可证，校验通过才出现在首页 |
| `app/library.py` | 「我的书库」：导入、预览、删除、排序、用系统程序打开（`--library` 才启用） |
| `open_in_reader.py` | 资源管理器右键「用阅读器打开」的入口脚本 |
| `static/` | 前端（无构建步骤）：`app.js` 目录树/路由/搜索/进度、`companion.js` 陪读、`renderers.js` 渲染器、`ide/` 编辑器、`m/` 手机版、`mybooks/` 书库 |
| `tests/` | 服务端回归测试（纯标准库 unittest） |
| `dev/` | 开发工具：`gen-roadmap.js` 生成首页数据、`test-render.js` 前端渲染测试、图标脚本 |

### 想改某个东西

| 目标 | 位置 |
|---|---|
| 加一个 API 路由 | `server.py` → `Handler._route` / `_route_post` |
| 加一种文件类型渲染 | `static/renderers.js` + `server.py` 的 `KIND_MAP` / `LANG_MAP` |
| 改默认端口 / 资料根 | `server.py` 顶部 `PORT`、`STUDYAI_ROOT` 环境变量 |
| 改陪读提示词 / 预设服务商 | `app/ai.py` 的 `build_system_prompt` / `AI_PRESETS` |
| 改手机版 | `static/m/`（独立外壳，不与桌面版共享布局） |

---

## 三、测试

```powershell
python -m unittest discover -s tests -v     # 服务端，22 项
cd dev; node test-render.js              # 前端渲染，28 项（需要 node_modules）
```

测试会自建临时资料根，**不会碰**真实课程、书库和 `data/ai-config.json`。

---

## 四、安全边界（有意为之）

| 项 | 做法 |
|---|---|
| 监听 | 默认只有 `127.0.0.1` |
| 路径 | `realpath` 解析后必须落在资料根内，越界抛 `UnsafePath` |
| 敏感文件 | `_webapp/`、`logs/`、`dev/`、`data/`、`.git/` 等一律不从 HTTP 提供 |
| 密钥 | 只存本机 `data/ai-config.json`（已 gitignore），接口只回显掩码；服务端不转发给浏览器 |
| 大文件 | 文本 >8 MB 不读，二进制 >64 MB 不传 |

> `data/ai-config.json` 与 `data/lan-token` 都属于**机器本地配置**，不要提交、不要外发。

---

## 五、代码编辑器（`/ide`）

`/ide?path=<相对路径>` 是一个**独立的只读预览页**，用
[Monaco Editor](https://microsoft.github.io/monaco-editor/)（VSCode 的编辑器内核，MIT 许可）
打开任意文本文件，带语法高亮、查找替换、多光标、代码折叠、行号。

| 项 | 现状 |
|---|---|
| 打开方式 | ① **顶栏 ✎**（与其它图标同尺寸）→ 在**右侧分栏**打开：已打开文件就编辑它，否则显示练习区文件列表<br>② **首页「练习区」板块** → 同样在右侧分栏打开<br>③ **文件标题栏 ✎** → 分栏编辑当前文件<br>④ `Ctrl+E` 同上 |
| 窄屏 | 窗口 < 900px 时自动改为新标签打开，避免分栏被压扁 |
| 能力 | 打开、编辑、高亮、搜索替换、**保存**（Ctrl+S）、**运行**（Ctrl+Enter）、输出面板 |
| 保存位置 | **只能写工作区**（默认 `练习区/`，可在 ⚙ 里改）；课程正文永远只读 |
| 运行 | 用可配置的 Python 解释器（默认就是跑本服务那个），带超时强杀与输出截断 |
| 开关 | 默认关闭，需 `python server.py --ide` 才出现（见下） |
| 资源 | `static/vendor/monaco/vs`，4.3 MB（已裁掉多余语言包与非中文 nls） |

### 为什么默认关闭

`--ide` 等于对外提供「保存任意文件 + 执行任意 Python」的接口。所以：

- 不加 `--ide` 就完全没有这些路由，页面只提示未启用；
- `--ide` **不能**和 `--lan` / `--bind` 同时用（那等于把代码执行开放给局域网，启动时直接拒绝）；
- 保存路径强制校验在工作区内，`../`、绝对路径、盘符一律拒绝；
- 运行超时（默认 10 秒）会连同子进程一起杀掉，输出最多保留 200 KB。

### 保存对话框

第一次保存（或对课程文件点「保存」）会弹出对话框：**选目录 + 填文件名 + 勾选「记住这个目录」**。
目录列表来自工作区里已有的子目录；想建新目录，直接在文件名里写 `子目录/名字.py`。
勾了「记住」之后，下次保存默认就落在这个目录。

### 可配置项（`_webapp/data/ide-config.json`，已 gitignore）

| 项 | 默认 | 说明 |
|---|---|---|
| `workspace` | `练习区` | 工作区，相对资料根，必须在资料根内 |
| `defaultDir` | 空 | 工作区内的默认保存子目录（保存对话框里勾「记住」就会写这里） |
| `python` | 空 | 空 = 用当前解释器；可填 Anaconda 等绝对路径 |
| `timeout` | `10` | 运行超时秒数（1–120） |

改法有两种：页面右上角 ⚙，或直接 `POST /api/ide/config`。

### 重新裁剪 Monaco（升级时）

```powershell
cd dev
npm install monaco-editor@0.45.0
# 只拷 loader.js + editor/ + base/ + 需要的 basic-languages/<语言>，
# 删掉 editor.main.nls.<非中文>.js 与 *.map，放到 static/vendor/monaco/vs
```

> **为什么不走 `vscode://` 协议**：那要求每台机器都装 VSCode，等于把"读讲义"绑死在桌面 IDE 上。
> Monaco 是纯前端资源，手机和任何浏览器都能用，且断网可用。

---

## 六、脚本文件的行尾约定

| 类型 | 行尾 | BOM |
|---|---|---|
| `.bat` | 必须 CRLF | 必须无 BOM |
| `.ps1` | CRLF 即可 | 必须带 BOM（PowerShell 5.1 否则按 GBK 解析中文） |
| `.py` / `.md` / `.js` | LF 即可 | 无 BOM |

改完 `.bat` 可用 `docs/维护笔记.md` 里的校验片段确认裸 LF = 0。
