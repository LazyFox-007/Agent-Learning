# 第三方内容声明

本仓库的**平台代码**（`_webapp/`、`_scripts/`、`setup.ps1`）为本项目原创，
采用 [MIT License](LICENSE) 授权。

以下为随附或引用的第三方内容。

---

## 课程内容（随本仓库分发）

| 项 | 说明 |
|---|---|
| 名称 | AI Agent 全栈课程 |
| 仓库 | https://github.com/callous-0923/agent-study |
| 作者 | [callous-0923](https://github.com/callous-0923) |
| 协议 | MIT License |
| 规模 | 37 章（Ch0–Ch36），38 份讲义 + 37 个可运行 Python 源码 |
| 位置 | [`01-AI-Agent全栈课程/`](01-AI-Agent全栈课程/) |

**课程正文随本仓库一起分发**，目的是让克隆下来即可离线阅读，不必依赖网络。

引入时只做了三处**关乎离线可用的技术转换**，**未修改任何课程实质内容**：

1. 讲义中硬编码的绝对 URL 改写为相对路径（1,661 处）—— 否则断网后侧栏和上下章无法跳转
2. 移除 busuanzi 访问量统计脚本（38 页）—— 外部 CDN，本地无意义
3. 生成一份中文目录 `README.md` —— 便于阅读

上游原始 `LICENSE`（MIT, Copyright © 2026 Callous-0923）与署名完整保留在
[`01-AI-Agent全栈课程/LICENSE`](01-AI-Agent全栈课程/LICENSE)。
课程内容的著作权归原作者所有，本项目不对其主张任何权利。

`setup.ps1` 的作用是**更新**课程：从上游重新拉取最新版本并重复上述转换。
课程目录已存在时会自动跳过，不会覆盖。

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
