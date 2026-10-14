# 第三方内容声明

本仓库的**平台代码**（`_webapp/`、`_scripts/`、`setup.ps1`）为本项目原创，
采用 [MIT License](LICENSE) 授权。

以下为随附或引用的第三方内容。

---

## 课程内容（不随本仓库分发）

| 项 | 说明 |
|---|---|
| 名称 | AI Agent 全栈课程 |
| 仓库 | https://github.com/callous-0923/agent-study |
| 作者 | [callous-0923](https://github.com/callous-0923) |
| 协议 | MIT License |
| 规模 | 37 章（Ch0–Ch36），含可运行 Python 源码 |

**本仓库不包含课程正文。** `setup.ps1` 会通过 `git clone` 从上游拉取并做本地化转换
（绝对 URL 改写为相对路径、移除外部分析脚本），**不修改课程实质内容**，
并完整保留上游的 `LICENSE` 与署名。

---

## 前端依赖（`_webapp/static/vendor/`）

| 库 | 版本来源 | 协议 |
|---|---|---|
| [marked](https://github.com/markedjs/marked) | marked.min.js | MIT |
| [KaTeX](https://github.com/KaTeX/KaTeX) | katex.min.js · katex.min.css · auto-render.min.js | MIT |
| [highlight.js](https://github.com/highlightjs/highlight.js) | highlight.min.js · hljs-light.css · hljs-dark.css | BSD-3-Clause |

### 字体

`_webapp/static/vendor/fonts/` 下的 KaTeX 字体文件随 KaTeX 一同分发，
版权归 KaTeX 项目及各自字体作者所有，遵循 SIL Open Font License 1.1。

---

## 吉祥物

`_webapp/assets/` 下的吉祥物图片由本项目作者提供，采用与本项目相同的 MIT License。

---

*本文件仅作声明用途。各第三方组件的完整许可条款请参见其原始仓库。*
