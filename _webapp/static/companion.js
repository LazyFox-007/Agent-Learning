/* =====================================================================
   agent学习平台 · AI 陪读（大肥鱼）

   坐在右侧的陪读面板：
     - 知道你在读哪一章、哪个小节、选中了哪段
     - 流式回答，边写边显示
     - 每章独立的对话与笔记，跟着章节走
     - 选中讲义里的文字 → 冒泡「问大肥鱼」
   ===================================================================== */
(function () {
  'use strict';

  var R = window.Renderers;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  var LS = {
    open: 'cp.open',
    tab: 'cp.tab',
    hist: 'cp.hist.',   // + path
    note: 'cp.note.'    // + path
  };

  var CP = {
    el: {},
    cfg: null,
    presets: {},
    presetKey: '',      // 设置里当前选中的服务商
    ctx: { path: '', chapter: '', heading: '', progress: '', selection: '' },
    msgs: [],           // 当前章节的对话
    noteTimer: null,
    busy: false,
    xhr: null,
    open: false,
    tab: 'chat'
  };

  /* ------------------------------------------------------------------
     工具
     ------------------------------------------------------------------ */
  function esc(s) { return R && R.esc ? R.esc(s) : String(s); }

  function lsGet(k, d) {
    try { var v = localStorage.getItem(k); return v == null ? d : v; } catch (e) { return d; }
  }
  function lsSet(k, v) {
    try { localStorage.setItem(k, v); } catch (e) {}
  }

  function histKey() { return LS.hist + (CP.ctx.path || '__none__'); }
  function noteKey() { return LS.note + (CP.ctx.path || '__none__'); }

  function nowTime() {
    var d = new Date();
    return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
  }

  /* ------------------------------------------------------------------
     上下文：让 AI 知道你在读什么
     ------------------------------------------------------------------ */
  function chapterFromPath(path) {
    if (!path) return '';
    // 优先从 roadmap 数据里取正式章节名
    var RM = window.ROADMAP || {};
    var stages = RM.stages || [];
    for (var i = 0; i < stages.length; i++) {
      var items = stages[i].items || [];
      for (var j = 0; j < items.length; j++) {
        if (items[j].path === path) {
          return '第 ' + items[j].no + ' 章 · ' + items[j].title;
        }
      }
    }
    // 兜底：从路径猜
    var m = path.match(/chapter_(\d+)_([^/]+)\//);
    if (m) {
      return '第 ' + parseInt(m[1], 10) + ' 章 · ' + m[2].replace(/_/g, ' ');
    }
    if (path === 'README.md') return '资料库说明';
    return path.split('/').pop().replace(/\.[^.]+$/, '');
  }

  function getIframe() {
    return $('#doc iframe.html-view');
  }

  /* 当前可见的最近标题（md 与 iframe 都支持） */
  function visibleHeading() {
    var ifr = getIframe();
    if (ifr) {
      try {
        var doc = ifr.contentDocument;
        if (!doc) return '';
        var hs = Array.prototype.slice.call(doc.querySelectorAll('h1,h2,h3'));
        if (!hs.length) return '';
        // 取第一个仍在视口上方的标题
        var best = '';
        for (var i = 0; i < hs.length; i++) {
          var top = hs[i].getBoundingClientRect().top;
          if (top < 160) best = (hs[i].textContent || '').trim();
          else break;
        }
        return (best || (hs[0].textContent || '')).slice(0, 80);
      } catch (e) { return ''; }
    }
    // Markdown 渲染的文档
    var doc = $('#doc');
    if (!doc) return '';
    var all = $$('h1,h2,h3', doc);
    var cur = '';
    var base = doc.getBoundingClientRect().top;
    for (var k = 0; k < all.length; k++) {
      if (all[k].getBoundingClientRect().top - base < 160) cur = (all[k].textContent || '').trim();
      else break;
    }
    return cur.slice(0, 80);
  }

  /* 抽取本章正文（用于"总结/出题"这类需要全文的请求） */
  function getExcerpt(limit) {
    limit = limit || 9000;
    var text = '';
    var ifr = getIframe();
    if (ifr) {
      try {
        var d = ifr.contentDocument;
        if (d && d.body) text = d.body.innerText || d.body.textContent || '';
      } catch (e) {}
    }
    if (!text) {
      var doc = $('#doc');
      if (doc) text = doc.innerText || doc.textContent || '';
    }
    text = text.replace(/\n{3,}/g, '\n\n').trim();
    return text.slice(0, limit);
  }

  /* 从 app.js 调用：打开新文件时更新陪读上下文 */
  function updateContext(file) {
    if (!file) {
      CP.ctx = { path: '', chapter: '', heading: '', progress: '', selection: '' };
      renderCtx();
      return;
    }
    CP.ctx.path = file.path || '';
    CP.ctx.chapter = chapterFromPath(file.path);
    CP.ctx.selection = '';
    // 换章节后 iframe 会重建，选区监听必须重新挂到新的 contentDocument 上
    if (CP.rebindSelection) {
      try { CP.rebindSelection(); } catch (e) {}
      setTimeout(function () {
        try { CP.rebindSelection(); } catch (e) {}
      }, 400);
    }
    // 等 iframe / 文档渲染完再取标题
    setTimeout(function () {
      CP.ctx.heading = visibleHeading();
      renderCtx();
    }, 300);

    loadHistory();
    loadNote();
    renderCtx();
    renderMsgs();
    renderQuick();
  }

  function renderCtx() {
    var el = CP.el.ctx;
    if (!el) return;
    if (!CP.ctx.path) {
      el.textContent = '未打开文件 · 随便聊聊';
      el.title = '';
      return;
    }
    var t = CP.ctx.chapter || CP.ctx.path;
    if (CP.ctx.heading) t = CP.ctx.heading;
    el.textContent = '陪读中 · ' + t;
    el.title = CP.ctx.chapter + '\n' + CP.ctx.path;
  }

  /* ------------------------------------------------------------------
     对话记录
     ------------------------------------------------------------------ */
  function loadHistory() {
    try {
      var raw = lsGet(histKey(), '[]');
      var arr = JSON.parse(raw);
      // 只保留 user / assistant，且限制条数
      CP.msgs = (Array.isArray(arr) ? arr : [])
        .filter(function (m) { return m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string'; })
        .slice(-40);
    } catch (e) { CP.msgs = []; }
  }

  function saveHistory() {
    try {
      lsSet(histKey(), JSON.stringify(CP.msgs.slice(-40)));
    } catch (e) { /* 超配额时静默降级 */ }
  }

  function loadNote() {
    var ta = CP.el.note;
    if (!ta) return;
    ta.value = lsGet(noteKey(), '');
  }

  /* ------------------------------------------------------------------
     渲染消息
     ------------------------------------------------------------------ */
  function clearMsgs() {
    CP.msgs = [];
    saveHistory();
    renderMsgs();
  }

  function renderMsgs() {
    var box = CP.el.msgs;
    if (!box) return;
    if (!CP.msgs.length) {
      renderEmptyState();
      return;
    }
    box.innerHTML = CP.msgs.map(function (m, i) {
      return msgHtml(m, i);
    }).join('');
    bindMsgActions(box);
    scrollBottom();
  }

  /* 空对话时的引导。未连接真实模型就先把「连接」摆在最显眼的位置 */
  function renderEmptyState() {
    var box = CP.el.msgs;
    if (!box) return;
    var c = CP.cfg || {};
    var isMock = String(c.base_url || '').indexOf('mock://') === 0;
    var noKey = !isMock && !c.configured;

    var cta = '';
    if (isMock) {
      cta =
        '<button class="cp-cta" id="cpCtaSetup">' +
          '<span class="cp-cta-ico">🔑</span>' +
          '<span class="cp-cta-txt"><b>连接真实模型</b><i>现在是演示模式，回答是固定示例</i></span>' +
          '<span class="cp-cta-arrow">→</span>' +
        '</button>';
    } else if (noKey) {
      cta =
        '<button class="cp-cta warn" id="cpCtaSetup">' +
          '<span class="cp-cta-ico">⚠️</span>' +
          '<span class="cp-cta-txt"><b>还没填 API Key</b><i>填上才能真的回答问题</i></span>' +
          '<span class="cp-cta-arrow">→</span>' +
        '</button>';
    }

    box.innerHTML =
      '<div class="cp-empty">' +
        '<img src="/static/mascot-64.png" class="cp-empty-fish" alt="">' +
        '<div class="cp-empty-t">大肥鱼在这儿</div>' +
        (cta ||
          '<div class="cp-empty-d">' +
            '在讲义里划一段文字，右边会冒出「问大肥鱼」；<br>' +
            '或者点下面的快捷指令，让我总结、出题、举例子。' +
          '</div>') +
      '</div>';

    var btn = $('#cpCtaSetup', box);
    if (btn) btn.addEventListener('click', openSettings);
  }

  function msgHtml(m, idx) {
    var isUser = m.role === 'user';
    var body = isUser
      ? '<div class="cp-bubble">' + esc(m.content).replace(/\n/g, '<br>') + '</div>'
      : '<div class="cp-bubble cp-md" data-md="' + idx + '">' +
          (m._streaming ? esc(m.content).replace(/\n/g, '<br>') : mdToHtml(m.content)) +
        '</div>';
    return '<div class="cp-msg ' + (isUser ? 'me' : 'ai') + '" data-idx="' + idx + '">' +
             (isUser ? '' : '<img class="cp-mini" src="/static/mascot-64.png" alt="">') +
             '<div class="cp-msgcol">' +
               body +
               '<div class="cp-meta">' +
                 '<span>' + esc(m.time || '') + '</span>' +
                 (!isUser ? '<button class="cp-copy" data-copy="' + idx + '" title="复制">⧉</button>' : '') +
               '</div>' +
             '</div>' +
           '</div>';
  }

  function mdToHtml(text) {
    try {
      if (R && R.renderMarkdown) {
        var out = R.renderMarkdown(text || '', '');
        return out && out.html ? out.html : esc(text || '');
      }
    } catch (e) {}
    return esc(text || '').replace(/\n/g, '<br>');
  }

  function bindMsgActions(box) {
    $$('.cp-copy', box).forEach(function (b) {
      b.addEventListener('click', function () {
        var m = CP.msgs[+b.dataset.copy];
        if (!m) return;
        var t = m.content;
        if (navigator.clipboard) navigator.clipboard.writeText(t);
      });
    });
  }

  function scrollBottom() {
    var box = CP.el.msgs;
    if (box) box.scrollTop = box.scrollHeight;
  }

  /* ------------------------------------------------------------------
     快捷指令
     ------------------------------------------------------------------ */
  var QUICK = [
    { id: 'explain',  label: '解释选中的', prompt: '请解释我选中的这段内容，讲清楚它在说什么、为什么重要。', need: 'selection' },
    { id: 'summary',  label: '总结本章',   prompt: '请总结本章的核心内容和结构，200 字以内，用要点列出。',   need: 'excerpt' },
    { id: 'quiz',     label: '出 3 道题',  prompt: '根据本章内容出 3 道题考我，先只出题不要给答案，等我回答后再点评。', need: 'excerpt' },
    { id: 'example',  label: '举例子',     prompt: '请用一个具体、可运行的代码例子说明本章的核心概念。', need: 'excerpt' },
    { id: 'weak',     label: '帮我找盲点', prompt: '本章最容易让人误解或忽略的点是什么？我该重点注意哪些地方？', need: 'chapter' },
    { id: 'next',     label: '下一步学什么', prompt: '学完本章后，按顺序下一章是什么？需要先补哪些前置知识？', need: 'chapter' }
  ];

  function renderQuick() {
    var box = CP.el.quick;
    if (!box) return;
    var hasSel = !!CP.ctx.selection;
    var hasDoc = !!CP.ctx.path;
    box.innerHTML = QUICK.map(function (q) {
      var able = q.need === 'selection' ? hasSel
               : q.need === 'excerpt'   ? hasDoc
               : hasDoc;
      return '<button class="cp-chip" data-qid="' + q.id + '"' + (able ? '' : ' disabled') + '>' +
             esc(q.label) + '</button>';
    }).join('');
    $$('.cp-chip', box).forEach(function (b) {
      b.addEventListener('click', function () {
        var q = QUICK.filter(function (x) { return x.id === b.dataset.qid; })[0];
        if (!q) return;
        send(q.prompt, { quick: q.id });
      });
    });
  }

  /* ------------------------------------------------------------------
     发送 & 流式接收
     ------------------------------------------------------------------ */
  function setBusy(on) {
    CP.busy = on;
    if (CP.el.send) {
      CP.el.send.disabled = on;
      CP.el.send.textContent = on ? '■' : '↑';
      CP.el.send.title = on ? '停止生成' : '发送 (Enter)';
    }
    if (CP.el.typing) CP.el.typing.hidden = !on;
  }

  function send(text, opts) {
    opts = opts || {};
    text = (text || '').trim();
    if (!text) return;
    if (CP.busy) { stop(); return; }

    // 给后端准备上下文；带 excerpt 的请求才拉全文，省 token
    var ctx = {
      path: CP.ctx.path,
      chapter: CP.ctx.chapter,
      heading: CP.ctx.heading,
      progress: CP.ctx.progress,
      selection: CP.ctx.selection || ''
    };
    if (opts.quick === 'summary' || opts.quick === 'quiz' || opts.quick === 'example' || opts.needExcerpt) {
      ctx.excerpt = getExcerpt(9000);
    } else if (CP.ctx.selection) {
      // 有选中时附上选中段落附近的内容即可
      ctx.excerpt = getExcerpt(3500);
    }

    CP.msgs.push({ role: 'user', content: text, time: nowTime() });
    saveHistory();
    renderMsgs();

    var aiMsg = { role: 'assistant', content: '', time: nowTime(), _streaming: true };
    CP.msgs.push(aiMsg);
    renderMsgs();
    setBusy(true);

    var payload = {
      messages: CP.msgs.filter(function (m) { return !m._streaming; }).map(function (m) {
        return { role: m.role, content: m.content };
      }),
      context: ctx
    };

    var xhr = new XMLHttpRequest();
    CP.xhr = xhr;
    xhr.open('POST', '/api/ai/chat', true);
    xhr.setRequestHeader('Content-Type', 'application/json');

    var lastLen = 0;

    xhr.onreadystatechange = function () {
      if (xhr.readyState === 3 || xhr.readyState === 4) {
        var buf = xhr.responseText || '';
        if (buf.length > lastLen) {
          var fresh = buf.slice(lastLen);
          lastLen = buf.length;
          handleSSE(fresh, aiMsg);
        }
        if (xhr.readyState === 4) {
          finish();
        }
      }
    };

    xhr.onerror = function () {
      aiMsg._streaming = false;
      aiMsg.content += '\n\n> ⚠️ 网络请求失败，检查服务是否还在运行。';
      finish();
    };

    function finish() {
      aiMsg._streaming = false;
      saveHistory();
      renderMsgs();
      setBusy(false);
      CP.xhr = null;
    }

    xhr.send(JSON.stringify(payload));
  }

  /* 处理 SSE 片段（可能一次拿到半条事件，要缓冲） */
  var sseBuf = '';
  function handleSSE(fresh, aiMsg) {
    sseBuf += fresh;
    var idx;
    while ((idx = sseBuf.indexOf('\n\n')) >= 0) {
      var block = sseBuf.slice(0, idx);
      sseBuf = sseBuf.slice(idx + 2);
      var lines = block.split('\n');
      for (var i = 0; i < lines.length; i++) {
        var line = lines[i];
        if (line.indexOf('data:') !== 0) continue;
        var data = line.slice(5).trim();
        if (!data) continue;
        var obj;
        try { obj = JSON.parse(data); } catch (e) { continue; }
        if (obj.type === 'delta' && obj.text) {
          aiMsg.content += obj.text;
          aiMsg._streaming = true;
          patchStreaming(aiMsg);
        } else if (obj.type === 'error') {
          aiMsg.content += '\n\n> ⚠️ ' + (obj.message || '未知错误');
          aiMsg._streaming = true;
          patchStreaming(aiMsg);
        } else if (obj.type === 'done') {
          aiMsg._streaming = false;
        }
      }
    }
  }

  /* 流式期间只更新那一条气泡的纯文本，避免整块重渲染 */
  function patchStreaming(aiMsg) {
    var box = CP.el.msgs;
    if (!box) return;
    var el = box.querySelector('.cp-msg:last-child .cp-bubble');
    if (!el) { renderMsgs(); return; }
    el.textContent = aiMsg.content;
    scrollBottom();
  }

  function stop() {
    if (CP.xhr) {
      try { CP.xhr.abort(); } catch (e) {}
      CP.xhr = null;
    }
    setBusy(false);
    for (var i = CP.msgs.length - 1; i >= 0; i--) {
      if (CP.msgs[i]._streaming) { CP.msgs[i]._streaming = false; break; }
    }
    saveHistory();
    renderMsgs();
  }

  /* ------------------------------------------------------------------
     选中文字 → 冒泡「问大肥鱼」
     ------------------------------------------------------------------ */
  function initSelectionChip() {
    var chip = CP.el.chip;
    if (!chip) return;

    var selTimer = null;

    // 父文档：Markdown / 代码这类直接渲染的内容
    document.addEventListener('mouseup', onMouseUp, true);
    document.addEventListener('keyup', onKeyUp, true);
    // 手机上长按选词主要触发 selectionchange，mouseup 不一定有，
    // 所以父文档也必须监听（数学页走的就是这条路）
    document.addEventListener('selectionchange', function () {
      if (document.activeElement && /INPUT|TEXTAREA/.test(document.activeElement.tagName)) return;
      clearTimeout(selTimer);
      selTimer = setTimeout(function () { probeSelection(null); }, 240);
    });

    /* iframe 内部：课程讲义全在这里面。
       iframe 里的鼠标事件不会冒泡到父文档，必须在 contentDocument 上单独监听，
       否则划线永远等不到 mouseup —— 这正是「划词问大肥鱼」失效的原因。 */
    function bindIframeDoc(ifr) {
      var idoc = null;
      try { idoc = ifr.contentDocument; } catch (e) { return; }
      if (!idoc || idoc.__cpSelBound) return;
      idoc.__cpSelBound = true;

      idoc.addEventListener('mouseup', onMouseUp, true);
      idoc.addEventListener('keyup', onKeyUp, true);
      idoc.addEventListener('scroll', function () { hideChip(); }, true);
      // 键盘选择、双击选词这类没有 mouseup 的场景
      idoc.addEventListener('selectionchange', function () {
        clearTimeout(selTimer);
        selTimer = setTimeout(function () { probeSelection(null); }, 240);
      });
    }

    function bindSelectionTargets() {
      var ifr = getIframe();
      if (!ifr) return;
      if (!ifr.__cpLoadBound) {
        ifr.__cpLoadBound = true;
        // 新章节会重建 iframe，load 时 contentDocument 才指向真正的文档
        ifr.addEventListener('load', function () { bindIframeDoc(ifr); });
      }
      bindIframeDoc(ifr);
    }

    // 暴露给 updateContext：换章节后重新绑定
    CP.rebindSelection = bindSelectionTargets;
    bindSelectionTargets();

    function onMouseUp(ev) {
      setTimeout(function () { probeSelection(ev); }, 0);
    }
    function onKeyUp(ev) {
      if (ev.key === 'Shift' || ev.key === 'ArrowLeft' || ev.key === 'ArrowRight' ||
          ev.key === 'ArrowUp' || ev.key === 'ArrowDown') {
        setTimeout(function () { probeSelection(ev); }, 0);
      }
    }

    function probeSelection(ev) {
      var winSel = window.getSelection ? window.getSelection() : null;
      var sel = String(winSel || '').trim();
      var rect = null;

      var ifr = getIframe();
      if (ifr) {
        try {
          var idoc = ifr.contentDocument;
          var isel = idoc && idoc.getSelection ? String(idoc.getSelection()).trim() : '';
          if (isel && isel.length >= 2) {
            sel = isel;
            var range = idoc.getSelection().getRangeAt(0);
            var r = range.getBoundingClientRect();
            var base = ifr.getBoundingClientRect();
            rect = { left: base.left + r.left, top: base.top + r.top, width: r.width, height: r.height };
          }
        } catch (e) {}
      }

      if (!rect && sel && sel.length >= 2) {
        if (winSel && winSel.rangeCount) {
          var r2 = winSel.getRangeAt(0).getBoundingClientRect();
          rect = { left: r2.left, top: r2.top, width: r2.width, height: r2.height };
        }
      }

      if (!sel || !rect || sel.length < 2) { hideChip(); return; }

      CP.ctx.selection = sel.slice(0, 3000);
      chip.dataset.sel = CP.ctx.selection;
      chip.hidden = false;
      // 冒泡画在父页面坐标系里，要避开顶部工具栏
      var top = Math.max(8, rect.top - 42);
      var left = Math.min(window.innerWidth - 160, Math.max(8, rect.left + rect.width / 2 - 62));
      chip.style.top = top + 'px';
      chip.style.left = left + 'px';
      renderQuick();
    }

    // 点到别处就收起（点到冒泡本身除外）
    document.addEventListener('mousedown', function (ev) {
      if (!chip.hidden && ev.target !== chip && !chip.contains(ev.target)) hideChip();
    }, true);
    var _ifrForHide = getIframe();
    if (_ifrForHide) {
      try {
        _ifrForHide.addEventListener('load', function () {
          var d = null;
          try { d = _ifrForHide.contentDocument; } catch (e) { return; }
          if (d) d.addEventListener('mousedown', function () { hideChip(); }, true);
        });
      } catch (e) {}
    }

    chip.addEventListener('click', function () {
      var sel = chip.dataset.sel || '';
      var at = { top: parseInt(chip.style.top, 10) || 80, left: parseInt(chip.style.left, 10) || 40 };
      hideChip();
      // 划词问答：就地弹一个小气泡直接出答案，不打开全屏面板
      askInline(sel, at);
    });

    window.addEventListener('scroll', hideChip, true);
  }

  function hideChip() {
    if (CP.el.chip) CP.el.chip.hidden = true;
  }

  /* ------------------------------------------------------------------
     划词快答：在选区旁边弹一个小气泡，直接流式出答案，不打开全屏面板
     ------------------------------------------------------------------ */
  var _inlineEl = null;      // 气泡根节点
  var _inlineXhr = null;

  function closeInline() {
    if (_inlineXhr) { try { _inlineXhr.abort(); } catch (e) {} _inlineXhr = null; }
    if (_inlineEl) { _inlineEl.remove(); _inlineEl = null; }
  }

  function inlineBubble() {
    if (_inlineEl) return _inlineEl;
    var el = document.createElement('div');
    el.className = 'cp-inline';
    el.innerHTML =
      '<div class="cp-inline-head">' +
        '<img src="/static/mascot-64.png" alt="">' +
        '<b>大肥鱼</b>' +
        '<button class="cp-inline-x" title="关闭">✕</button>' +
      '</div>' +
      '<div class="cp-inline-body"><span class="cp-inline-dots"><i></i><i></i><i></i></span></div>' +
      '<div class="cp-inline-foot"><button class="cp-inline-more">在陪读面板里继续 →</button></div>';
    document.body.appendChild(el);
    el.querySelector('.cp-inline-x').addEventListener('click', closeInline);
    el.querySelector('.cp-inline-more').addEventListener('click', function () {
      var q = el.dataset.q || '';
      closeInline();
      if (!CP.open) openPanel();
      if (CP.tab !== 'chat') switchTab('chat');
      if (q) send(q, {});
    });
    _inlineEl = el;
    return el;
  }

  function askInline(sel, at) {
    sel = String(sel || '').trim();
    if (!sel) return;
    closeInline();
    var el = inlineBubble();
    el.dataset.q = '请解释我选中的这段内容：\n\n> ' + sel.replace(/\n/g, '\n> ');
    el.dataset.sel = sel;
    placeInline(el, at);

    var body = el.querySelector('.cp-inline-body');

    // 后端需要当前章节上下文，和面板用的是同一套
    var ctx = {
      path: CP.ctx.path, chapter: CP.ctx.chapter,
      heading: CP.ctx.heading, progress: CP.ctx.progress,
      selection: sel
    };

    var text = '';
    var xhr = new XMLHttpRequest();
    _inlineXhr = xhr;
    xhr.open('POST', '/api/ai/chat', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    var lastLen = 0;

    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 3 && xhr.readyState !== 4) return;
      var raw = '';
      try { raw = xhr.responseText || ''; } catch (e) { return; }
      var chunk = raw.slice(lastLen);
      lastLen = raw.length;
      if (!chunk) return;

      var evs = chunk.split('\n\n');
      evs.forEach(function (ev) {
        var line = ev.split('\n').filter(function (l) { return l.indexOf('data:') === 0; })[0];
        if (!line) return;
        var obj;
        try { obj = JSON.parse(line.slice(5).trim()); } catch (e) { return; }
        if (obj.type === 'delta' && obj.text) {
          text += obj.text;
          body.textContent = text;
          body.scrollTop = body.scrollHeight;
        } else if (obj.type === 'error') {
          body.innerHTML = '<span class="cp-inline-err">❌ ' + esc(obj.message || '出错了') +
            (obj.hint ? '<br>💡 ' + esc(obj.hint) : '') + '</span>';
        } else if (obj.type === 'done') {
          if (window.Renderers && Renderers.renderMarkdown) {
            try {
              var r = Renderers.renderMarkdown(text, CP.ctx.path ? CP.ctx.path.split('/').slice(0, -1).join('/') : '');
              body.innerHTML = '<div class="cp-md">' + r.html + '</div>';
            } catch (e) { body.textContent = text; }
          } else { body.textContent = text; }
        }
      });
      placeInline(el, at);
    };

    xhr.onerror = function () {
      body.innerHTML = '<span class="cp-inline-err">❌ 连不上本地服务</span>';
    };

    xhr.send(JSON.stringify({
      messages: [{ role: 'user', content: el.dataset.q }],
      context: ctx
    }));

    // 点别处关闭
    setTimeout(function () {
      document.addEventListener('mousedown', function once(e) {
        if (_inlineEl && !_inlineEl.contains(e.target)) {
          closeInline();
          document.removeEventListener('mousedown', once, true);
        }
      }, true);
    }, 100);
  }

  /* 把气泡摆到选区附近，保证完整显示在屏幕内。
     手机上的坑：
       · 100vh 含浏览器地址栏，实际可见高度小得多 → 用 visualViewport
       · 答案流式变长时高度一直在变 → 每次都要重新夹一次
       · 上方放不下就翻到选区下方，下方也放不下就贴顶/贴底 */
  function placeInline(el, at) {
    var vv = window.visualViewport;
    var vw = (vv && vv.width) || window.innerWidth;
    var vh = (vv && vv.height) || window.innerHeight;
    var offTop = (vv && vv.offsetTop) || 0;
    var offLeft = (vv && vv.offsetLeft) || 0;

    var GAP = 10;
    var avail = vh - GAP * 2;                 // 真正能用的高度

    // 先限制最大高度，避免内容把气泡撑出屏幕
    el.style.maxHeight = Math.min(avail, Math.round(vh * 0.66)) + 'px';

    var w = el.offsetWidth || Math.min(340, vw - 20);
    var h = el.offsetHeight || 160;

    var left = Math.round(at.left - w / 2 + 60);
    left = Math.max(GAP + offLeft, Math.min(vw - w - GAP + offLeft, left));

    // 优先放在选区上方
    var top = at.top - h - 14;
    if (top < GAP + offTop) {
      // 上方不够 → 放到选区下方
      var below = at.top + 52;
      if (below + h > vh - GAP + offTop) {
        // 上下都放不下 → 贴顶（内容自己滚动）
        top = GAP + offTop;
      } else {
        top = below;
      }
    }
    top = Math.max(GAP + offTop, Math.min(vh - h - GAP + offTop, top));

    el.style.left = left + 'px';
    el.style.top = top + 'px';
  }

  /* ------------------------------------------------------------------
     设置：服务商卡片 + 高级折叠 + 保存并测试
     ------------------------------------------------------------------ */
  var BADGE_TEXT = { free: '免费', cheap: '便宜', paid: '需付费', demo: '不联网' };
  var PRESET_ORDER = ['deepseek', 'qwen', 'moonshot', 'ollama', 'openai', 'mock'];

  // 不需要 API Key 的服务商
  function needsKey(k) { return k !== 'mock' && k !== 'ollama'; }

  function setTestOut(text, cls) {
    var out = CP.el.testOut;
    if (!out) return;
    out.textContent = text || '';
    out.className = 'cp-test-out' + (cls ? ' ' + cls : '');
  }

  function renderProviders() {
    var box = CP.el.providers;
    if (!box) return;
    var keys = Object.keys(CP.presets).sort(function (a, b) {
      var ia = PRESET_ORDER.indexOf(a), ib = PRESET_ORDER.indexOf(b);
      return (ia < 0 ? 8 : ia) - (ib < 0 ? 8 : ib);
    });
    box.innerHTML = keys.map(function (k) {
      var p = CP.presets[k];
      var on = CP.presetKey === k;
      var badge = BADGE_TEXT[p.badge] || '';
      return '<button type="button" class="cp-prov' + (on ? ' on' : '') + '" data-preset="' + esc(k) + '">' +
        '<span class="cp-prov-top"><b>' + esc(p.name) + '</b>' +
        (badge ? '<i class="cp-prov-badge b-' + esc(p.badge) + '">' + esc(badge) + '</i>' : '') +
        '</span>' +
        '<span class="cp-prov-desc">' + esc(p.desc || '') + '</span>' +
        '</button>';
    }).join('');
  }

  function selectPreset(k) {
    var p = CP.presets[k];
    if (!p) return;
    CP.presetKey = k;
    renderProviders();

    if (CP.el.baseUrl) CP.el.baseUrl.value = p.base_url || '';
    if (CP.el.model) CP.el.model.value = p.model || '';

    var link = CP.el.getKey;
    if (link) {
      if (p.home) { link.href = p.home; link.hidden = false; }
      else { link.hidden = true; link.removeAttribute('href'); }
    }
    if (CP.el.keyField) CP.el.keyField.hidden = !needsKey(k);
    if (CP.el.keyHint) CP.el.keyHint.textContent = p.key_hint || '';
  }

  function openSettings() {
    var m = CP.el.modal;
    if (!m) return;
    m.hidden = false;
    setTestOut('', '');

    fetch('/api/ai/config').then(function (r) { return r.json(); }).then(function (c) {
      CP.cfg = c;
      syncModeBadge();

      CP.presetKey = CP.presets[c.preset] ? c.preset : 'deepseek';
      selectPreset(CP.presetKey);

      // 已有自定义地址/模型时，覆盖回用户存的值（selectPreset 会用预设默认值）
      if (c.base_url) CP.el.baseUrl.value = c.base_url;
      if (c.model) CP.el.model.value = c.model;
      if (CP.el.key) {
        CP.el.key.value = '';
        CP.el.key.placeholder = c.key_masked ? ('已保存 ' + c.key_masked + '（留空则不改）') : '粘贴 API Key';
      }
      if (CP.el.temp) {
        CP.el.temp.value = c.temperature;
        CP.el.tempVal.textContent = Number(c.temperature).toFixed(1);
      }
      // 地址和预设不一致 → 自动展开高级，让用户看到真实配置
      var p = CP.presets[CP.presetKey];
      var custom = p && c.base_url && c.base_url !== p.base_url;
      if (CP.el.advanced) CP.el.advanced.open = !!custom;
    }).catch(function () {
      setTestOut('读取配置失败', 'bad');
    });
  }

  function closeSettings() {
    if (CP.el.modal) CP.el.modal.hidden = true;
    setTestOut('', '');
  }

  /* 顶栏状态标记：演示模式 / 未配置密钥，避免把假回答当成真的 */
  function syncModeBadge() {
    var el = CP.el.mode;
    if (!el) return;
    var c = CP.cfg || {};
    var isMock = String(c.base_url || '').indexOf('mock://') === 0;
    var noKey = !isMock && !c.configured;
    if (isMock) {
      el.hidden = false;
      el.textContent = '演示模式';
      el.className = 'cp-mode is-mock';
      el.title = '当前返回的是固定示例，不是真实模型回答。点 ⚙ 配置真实模型。';
    } else if (noKey) {
      el.hidden = false;
      el.textContent = '未配置';
      el.className = 'cp-mode is-warn';
      el.title = '还没填 API Key，点 ⚙ 设置';
    } else {
      el.hidden = true;
      el.textContent = '';
    }
  }

  function saveAndTest() {
    var body = {
      preset: CP.presetKey,
      base_url: CP.el.baseUrl ? CP.el.baseUrl.value.trim() : undefined,
      model: CP.el.model ? CP.el.model.value.trim() : undefined,
      temperature: CP.el.temp ? Number(CP.el.temp.value) : undefined
    };
    var k = CP.el.key ? CP.el.key.value.trim() : '';
    if (k) body.api_key = k;

    setTestOut('正在保存…', '');
    fetch('/api/ai/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); }).then(function (c) {
      CP.cfg = c;
      syncModeBadge();
      renderEmptyState();
      return runTest();
    }).then(function (ok) {
      if (ok) {
        setTimeout(function () { closeSettings(); toast('已连接，开始陪读'); }, 800);
      }
    }).catch(function () {
      setTestOut('保存失败，看看服务是不是停了', 'bad');
    });
  }

  // 返回 Promise<boolean>
  function runTest() {
    var body = {
      base_url: CP.el.baseUrl ? CP.el.baseUrl.value.trim() : '',
      model: CP.el.model ? CP.el.model.value.trim() : ''
    };
    var k = CP.el.key ? CP.el.key.value.trim() : '';
    if (k) body.api_key = k;

    setTestOut('正在测试连接…', '');
    return fetch('/api/ai/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); }).then(function (o) {
      if (o.ok) {
        setTestOut('✅ 连通（' + o.ms + 'ms）' + (o.reply ? ' · ' + o.reply : ''), 'ok');
        return true;
      }
      var msg = '❌ ' + (o.error || '连接失败');
      if (o.hint) msg += '\n💡 ' + o.hint;
      setTestOut(msg, 'bad');
      return false;
    }).catch(function (e) {
      setTestOut('❌ ' + e.message, 'bad');
      return false;
    });
  }

  function toast(msg) {
    var t = document.createElement('div');
    t.className = 'cp-toast';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () { t.classList.add('out'); }, 1600);
    setTimeout(function () { t.remove(); }, 2100);
  }

  /* ------------------------------------------------------------------
     面板开关 / 标签
     ------------------------------------------------------------------ */

  function openPanel() {
    CP.open = true;
    CP.el.root.hidden = false;
    document.body.classList.add('cp-open');
    lsSet(LS.open, '1');
    // 目录与陪读抢空间，自动收起目录
    var toc = $('#toc');
    if (toc && !toc.hidden) {
      toc.hidden = true;
      document.body.classList.add('cp-hid-toc');
    }
    if (CP.el.input) setTimeout(function () { CP.el.input.focus(); }, 120);
    renderCtx(); renderMsgs(); renderQuick();
  }

  function closePanel() {
    CP.open = false;
    CP.el.root.hidden = true;
    document.body.classList.remove('cp-open');
    lsSet(LS.open, '0');
    var toc = $('#toc');
    if (toc && document.body.classList.contains('cp-hid-toc')) {
      toc.hidden = false;
      document.body.classList.remove('cp-hid-toc');
    }
  }

  function togglePanel() {
    if (CP.open) closePanel(); else openPanel();
  }

  function switchTab(name) {
    CP.tab = name;
    lsSet(LS.tab, name);
    $$('.cp-tab').forEach(function (b) {
      b.classList.toggle('active', b.dataset.cptab === name);
    });
    if (CP.el.paneChat) CP.el.paneChat.hidden = name !== 'chat';
    if (CP.el.paneNote) CP.el.paneNote.hidden = name !== 'note';
    if (name === 'note' && CP.el.note) CP.el.note.focus();
  }

  /* ------------------------------------------------------------------
     初始化
     ------------------------------------------------------------------ */
  function init() {
    CP.el = {
      root:     $('#companion'),
      ctx:      $('#cpCtx'),
      mode:     $('#cpMode'),
      msgs:     $('#cpMsgs'),
      quick:    $('#cpQuick'),
      input:    $('#cpInput'),
      send:     $('#cpSend'),
      typing:   $('#cpTyping'),
      chip:     $('#cpSelChip'),
      modal:    $('#cpModal'),
      providers:$('#cpProviders'),
      getKey:   $('#cpGetKey'),
      keyField: $('#cpKeyField'),
      keyHint:  $('#cpKeyHint'),
      advanced: $('#cpAdvanced'),
      baseUrl:  $('#cpBaseUrl'),
      model:    $('#cpModel'),
      key:      $('#cpKey'),
      temp:     $('#cpTemp'),
      tempVal:  $('#cpTempVal'),
      testOut:  $('#cpTestOut'),
      note:     $('#cpNote'),
      paneChat: $('#cpPaneChat'),
      paneNote: $('#cpPaneNote'),
      btnClose: $('#cpClose'),
      btnSet:   $('#cpSettings'),
      btnClear: $('#cpClear')
    };
    if (!CP.el.root) return;

    // 预设表（服务商卡片的数据源）
    fetch('/api/ai/presets').then(function (r) { return r.json(); }).then(function (o) {
      CP.presets = o.presets || {};
      renderProviders();
    }).catch(function () {});

    // 关闭 / 设置 / 清空
    if (CP.el.btnClose) CP.el.btnClose.addEventListener('click', closePanel);
    if (CP.el.btnSet) CP.el.btnSet.addEventListener('click', openSettings);
    if (CP.el.btnClear) CP.el.btnClear.addEventListener('click', function () {
      if (CP.msgs.length && !confirm('清空本章的对话记录？')) return;
      clearMsgs(); renderQuick();
    });

    // 标签
    $$('.cp-tab').forEach(function (b) {
      b.addEventListener('click', function () { switchTab(b.dataset.cptab); });
    });

    // 输入
    if (CP.el.input) {
      CP.el.input.addEventListener('input', function () {
        CP.el.input.style.height = 'auto';
        CP.el.input.style.height = Math.min(140, CP.el.input.scrollHeight) + 'px';
      });
      CP.el.input.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' && !ev.shiftKey && !ev.isComposing) {
          ev.preventDefault();
          var v = CP.el.input.value;
          CP.el.input.value = '';
          CP.el.input.style.height = 'auto';
          send(v, {});
        }
      });
    }
    if (CP.el.send) CP.el.send.addEventListener('click', function () {
      if (CP.busy) { stop(); return; }
      var v = CP.el.input.value;
      CP.el.input.value = '';
      send(v, {});
    });

    // 笔记：防抖保存
    if (CP.el.note) {
      CP.el.note.addEventListener('input', function () {
        var v = CP.el.note.value;
        clearTimeout(CP.noteTimer);
        CP.noteTimer = setTimeout(function () {
          lsSet(noteKey(), v);
          CP.el.note.dataset.saved = '1';
          setTimeout(function () { delete CP.el.note.dataset.saved; }, 900);
        }, 400);
      });
    }

    // 设置对话框
    if (CP.el.modal) {
      var closeBtn = $('#cpModalClose');
      if (closeBtn) closeBtn.addEventListener('click', closeSettings);

      var saveBtn = $('#cpSave');
      if (saveBtn) saveBtn.addEventListener('click', saveAndTest);
      var testBtn = $('#cpTest');
      if (testBtn) testBtn.addEventListener('click', function () { runTest(); });

      CP.el.modal.addEventListener('click', function (ev) {
        if (ev.target === CP.el.modal) closeSettings();
      });

      // 服务商卡片：委托点击
      if (CP.el.providers) {
        CP.el.providers.addEventListener('click', function (ev) {
          var card = ev.target.closest('.cp-prov');
          if (!card) return;
          selectPreset(card.dataset.preset);
          setTestOut('', '');
          if (CP.el.key) CP.el.key.focus();
        });
      }

      if (CP.el.temp) {
        CP.el.temp.addEventListener('input', function () {
          CP.el.tempVal.textContent = Number(CP.el.temp.value).toFixed(1);
        });
      }

      // 在 Key 输入框里按回车 = 保存并测试
      if (CP.el.key) {
        CP.el.key.addEventListener('keydown', function (ev) {
          if (ev.key === 'Enter') { ev.preventDefault(); saveAndTest(); }
        });
      }
    }

    // 选中冒泡
    initSelectionChip();

    // 启动就读一次配置，顶栏才能立刻标出「演示模式 / 未配置」
    fetch('/api/ai/config')
      .then(function (r) { return r.json(); })
      .then(function (c) { CP.cfg = c; syncModeBadge(); })
      .catch(function () {});

    // 恢复上次状态
    switchTab(lsGet(LS.tab, 'chat'));
    if (lsGet(LS.open, '0') === '1') {
      // 稍等，等 app.js 把文档渲染出来再开
      setTimeout(openPanel, 500);
    }
  }

  window.Companion = {
    init: init,
    updateContext: updateContext,
    toggle: togglePanel,
    open: openPanel,
    close: closePanel,
    isOpen: function () { return CP.open; }
  };
})();
