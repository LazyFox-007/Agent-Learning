# AFA 与进程代数：从反基础公理到超集合语义

这是一套可自学、可授课的中文教材与课程材料，主题是 **Aczel 的反基础公理（AFA）** 及其在 **进程代数** 中的应用。

核心结论只有一句话：

> 把进程的迁移图装饰成超集合，**强互模拟就变成集合相等**。

## 目录里有什么

```
AFARules/
├─ README.md                 本文件
├─ 教学大纲.md               16 周课程大纲（学分、周次、考核、项目）
├─ book/                     教材源文件（Markdown + LaTeX 数学）
│  ├─ 90-前言.md
│  ├─ 00-导论.md
│  ├─ 01..12-第 1–12 章
│  └─ 91..94-附录 A–D
├─ figures/                  教材插图（PNG）
├─ build/                    构建脚本（DOCX / PDF / PPTX）
└─ out/                      成品
   ├─ AFA与进程代数-教材.docx
   ├─ AFA与进程代数-教材.pdf
   ├─ AFA与进程代数-课程讲义.pptx
   └─ AFA与进程代数-课程讲义.pdf
```

## 三种用法

**1. 直接阅读**：打开 `out/AFA与进程代数-教材.pdf`。PDF 带目录、页码与彩色定理框，适合打印或平板阅读。

**2. 修改后重编**：编辑 `book/*.md`，然后运行构建脚本（见下）。源文件用 Markdown + `$...$` 数学，GitHub/VSCode 可直接预览。

**3. 开课**：用 `教学大纲.md` 排课，用 `out/AFA与进程代数-课程讲义.pptx` 讲课。讲义共 30 余页，覆盖全书主线。

## 学习路径

- **标准（16 周）**：第 1–5 章（集合论与余代数）→ 第 6–10 章（进程代数）→ 第 11–12 章（统一与进阶）。
- **速成（6 周）**：第 1、2、3、4、6、7、11 章，抓住“装饰—互模拟—指称”主线。
- **研究入门**：在标准路径上加读第 5、8、9 章，并直接读 Aczel (1988)、Milner (1989)、Rutten (2000)。

## 章节地图

| 章 | 主题 | 关键结论 |
| --- | --- | --- |
| 0 | 导论 | 三个方程、三条线索 |
| 1 | 良基性与 FA | 良基装饰定理、Mostowski 坍缩 |
| 2 | 图、装饰与 AFA | 每个图有唯一装饰；Ω、Ω_∅ |
| 3 | 互模拟与超全集 | $d(x)=d(y)\iff x\sim y$ |
| 4 | 解引理与余归纳 | 方程有唯一解；余归纳证明 |
| 5 | 余代数与终余代数 | $(V_A,\mathrm{id})$ 是终余代数 |
| 6 | LTS 与强互模拟 | 游戏、HML、谱系 |
| 7 | CCS | 同余、展开律、RDP/RSP |
| 8 | 弱互模拟 | 观察同余、分支互模拟、τ 定律 |
| 9 | ACP | 公理系统、封装、抽象 |
| 10 | π-演算 | 名字传递、早/晚/开互模拟 |
| 11 | 进程即超集合 | 指称定理、语义三角 |
| 12 | 进阶 | AFA 变体、工具、前沿 |
| 附录 | A 公理速查 / B 习题解答 / C 术语表 / D 文献 | — |

## 重新构建

需要：Python 3.10+、`python-docx`、`python-pptx`、`Pillow`；本机安装 Microsoft Word（用于更新目录并导出 PDF）。

```powershell
# 1. 生成插图（可选，figures/ 已含成品）
python build/make_figures.py

# 2. 生成 DOCX
python build/build_docx.py

# 3. 用 Word 更新目录并导出 PDF
powershell -File build/export_pdf.ps1 `
  -Docx "out/AFA与进程代数-教材.docx" `
  -Pdf  "out/AFA与进程代数-教材.pdf"

# 4. 生成讲义 PPTX
python build/build_pptx.py
```

## 说明

- 本书是学习材料，不是原创研究；定理均来自 Aczel、Barwise–Moss、Milner、Rutten 等前辈的工作，书中做了整理与重述。
- 数学排版使用 Unicode + Cambria Math；源文件保留 LaTeX 记法，便于在 Markdown 中渲染。
- 若发现错误，欢迎在源文件中直接修改并重编。
