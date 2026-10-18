/* =====================================================================
   StudyAI · 资源库
   平台目前承载多套学习资源，这里定义它们的展示信息。
   新增资源时：往 LIBRARY 里加一条即可，首页卡片与章节列表自动出现。
   ===================================================================== */
(function () {
  'use strict';

  var LIBRARY = [
    {
      id: 'agent',
      icon: '🤖',
      name: 'AI Agent 全栈课程',
      org: 'callous-0923',
      tags: ['简体中文', 'MIT'],
      level: '入门 → 专家',
      volume: '37 章 · 7 层',
      accent: 'blue',
      desc: '从裸写 ReAct 循环开始，经 Claude Code 架构逆向、MCP / A2A 协议、RAG 深度解析、Agentic Workflow 设计模式，直到纵深安全。每章都是可运行的 Python。',
      entry: '01-AI-Agent全栈课程/index.html',
      dir: '01-AI-Agent全栈课程',
      format: '自包含 HTML'
    },
    {
      id: 'afa',
      icon: '∞',
      name: 'AFA 与进程代数',
      org: '本地教材',
      tags: ['数学', '超集合'],
      level: '研究生入门',
      volume: '12 章 · 4 附录',
      accent: 'violet',
      desc: 'Aczel 的反基础公理及其在进程代数中的应用。核心只有一句话：把进程的迁移图装饰成超集合，强互模拟就变成集合相等。',
      entry: '02-AFA与进程代数/book/00-导论.md',
      dir: '02-AFA与进程代数',
      format: 'Markdown + KaTeX',
      extras: [
        { label: '教材 PDF', path: '02-AFA与进程代数/out/AFA与进程代数-教材.pdf' },
        { label: '课程讲义 PPTX', path: '02-AFA与进程代数/out/AFA与进程代数-课程讲义.pptx' },
        { label: '教学大纲', path: '02-AFA与进程代数/教学大纲.md' }
      ],
      // AFA 的章节目录是 md 文件，没有 roadmap，这里直接列
      chapters: [
        { no: '导论', title: '三个方程、三条线索', path: '02-AFA与进程代数/book/00-导论.md' },
        { no: '第 1 章', title: '良基性、基础公理与循环对象', path: '02-AFA与进程代数/book/01-第1章-良基性与基础公理.md' },
        { no: '第 2 章', title: '图、装饰与反基础公理', path: '02-AFA与进程代数/book/02-第2章-图装饰与反基础公理.md' },
        { no: '第 3 章', title: '互模拟与超全集', path: '02-AFA与进程代数/book/03-第3章-互模拟与超全集.md' },
        { no: '第 4 章', title: '解引理与余归纳', path: '02-AFA与进程代数/book/04-第4章-解引理与余归纳.md' },
        { no: '第 5 章', title: '余代数与终余代数', path: '02-AFA与进程代数/book/05-第5章-余代数与终余代数.md' },
        { no: '第 6 章', title: 'LTS 与强互模拟', path: '02-AFA与进程代数/book/06-第6章-进程与互模拟.md' },
        { no: '第 7 章', title: 'CCS', path: '02-AFA与进程代数/book/07-第7章-CCS.md' },
        { no: '第 8 章', title: '弱互模拟', path: '02-AFA与进程代数/book/08-第8章-弱互模拟.md' },
        { no: '第 9 章', title: 'ACP', path: '02-AFA与进程代数/book/09-第9章-ACP.md' },
        { no: '第 10 章', title: 'π-演算', path: '02-AFA与进程代数/book/10-第10章-pi演算.md' },
        { no: '第 11 章', title: '进程即超集合', path: '02-AFA与进程代数/book/11-第11章-进程即超集合.md' },
        { no: '第 12 章', title: '进阶：变体、工具与前沿', path: '02-AFA与进程代数/book/12-第12章-进阶.md' },
        { no: '附录 A', title: '公理速查', path: '02-AFA与进程代数/book/91-附录A-公理速查.md' },
        { no: '附录 B', title: '习题解答', path: '02-AFA与进程代数/book/92-附录B-习题解答.md' },
        { no: '附录 C', title: '术语表', path: '02-AFA与进程代数/book/93-附录C-术语表.md' },
        { no: '附录 D', title: '参考文献', path: '02-AFA与进程代数/book/94-附录D-参考文献.md' }
      ]
    }
  ];

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function href(p) { return '#/' + encodeURI(p); }

  function cardHtml(r) {
    var tags = (r.tags || []).map(function (t) {
      return '<i>' + esc(t) + '</i>';
    }).join('');
    var extras = (r.extras || []).map(function (e) {
      return '<a class="lib-extra" href="' + href(e.path) + '" data-internal="1">' + esc(e.label) + '</a>';
    }).join('');
    return '' +
      '<article class="lib-card lib-' + esc(r.accent) + '">' +
        '<div class="lib-head">' +
          '<span class="lib-ico">' + esc(r.icon) + '</span>' +
          '<div class="lib-title">' +
            '<h3>' + esc(r.name) + '</h3>' +
            '<div class="lib-meta">' + esc(r.org) + ' · ' + esc(r.level) + ' · ' + esc(r.volume) + '</div>' +
          '</div>' +
        '</div>' +
        '<div class="lib-tags">' + tags + '<i class="fmt">' + esc(r.format) + '</i></div>' +
        '<p class="lib-desc">' + esc(r.desc) + '</p>' +
        (extras ? '<div class="lib-extras">' + extras + '</div>' : '') +
        '<a class="lib-enter" href="' + href(r.entry) + '" data-internal="1">开始学习 →</a>' +
      '</article>';
  }

  function chapterListHtml(r) {
    if (!r.chapters) return '';
    var rows = r.chapters.map(function (c) {
      return '<a class="lib-ch" href="' + href(c.path) + '" data-internal="1">' +
               '<span class="lib-ch-no">' + esc(c.no) + '</span>' +
               '<span class="lib-ch-t">' + esc(c.title) + '</span>' +
             '</a>';
    }).join('');
    return '<div class="lib-chapters">' + rows + '</div>';
  }

  /* 渲染首页的「资源库」区块 */
  function render() {
    var grid = document.getElementById('libGrid');
    if (grid) grid.innerHTML = LIBRARY.map(cardHtml).join('');

    var sec = document.getElementById('libAfa');
    if (sec) {
      var afa = LIBRARY.filter(function (r) { return r.chapters; })[0];
      if (afa) {
        sec.innerHTML =
          '<h2 class="rm-h2">' + esc(afa.name) + ' · 目录</h2>' +
          '<div class="rm-sub">数学教材，公式用 KaTeX 渲染。也可以直接下 PDF 在平板上读。</div>' +
          chapterListHtml(afa);
      }
    }
  }

  window.LIBRARY = LIBRARY;
  window.LibraryRender = render;
})();
