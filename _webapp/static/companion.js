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
      box.innerHTML =
        '<div class="cp-empty">' +
          '<img src="/static/mascot-64.png" class="cp-empty-fish" alt="">' +
          '<div class="cp-empty-t">大肥鱼在这儿</div>' +
          '<div class="cp-empty-d">' +
            '在讲义里划一段文字，右边会冒出「问大肥鱼」；<br>' +
            '或者点下面的快捷指令，让我总结、出题、举例子。' +
          '</div>' +
        '</div>';
      return;
    }
    box.innerHTML = CP.msgs.map(function (m, i) {
      return msgHtml(m, i);
    }).join('');
    bindMsgActions(box);
    scrollBottom();
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

    document.addEventListener('mouseup', onMouseUp, true);

    function onMouseUp(ev) {
      setTimeout(function () { probeSelection(ev); }, 0);
    }

    function probeSelection(ev) {
      var sel = String(window.getSelection ? window.getSelection() : '').trim();
      var rect = null;

      var ifr = getIframe();
      if (ifr) {
        try {
          var idoc = ifr.contentDocument;
          var isel = idoc && idoc.getSelection ? String(idoc.getSelection()).trim() : '';
          if (isel && isel.length >= 8) {
            sel = isel;
            var range = idoc.getSelection().getRangeAt(0);
            var r = range.getBoundingClientRect();
            var base = ifr.getBoundingClientRect();
            rect = { left: base.left + r.left, top: base.top + r.top, width: r.width, height: r.height };
          }
        } catch (e) {}
      }

      if (!rect && sel && sel.length >= 8) {
        var s = window.getSelection();
        if (s && s.rangeCount) {
          var r2 = s.getRangeAt(0).getBoundingClientRect();
          rect = { left: r2.left, top: r2.top, width: r2.width, height: r2.height };
        }
      }

      if (!sel || !rect || sel.length < 8) { hideChip(); return; }

      CP.ctx.selection = sel.slice(0, 3000);
      chip.dataset.sel = CP.ctx.selection;
      chip.hidden = false;
      var top = Math.max(8, rect.top - 40);
      var left = Math.min(window.innerWidth - 150, Math.max(8, rect.left + rect.width / 2 - 60));
      chip.style.top = top + 'px';
      chip.style.left = left + 'px';
      renderQuick();
    }

    document.addEventListener('mousedown', function (ev) {
      if (ev.target !== chip) { /* 保留，等 selection 判断 */ }
    });

    chip.addEventListener('click', function () {
      var sel = chip.dataset.sel || '';
      hideChip();
      if (!CP.open) openPanel();
      if (CP.tab !== 'chat') switchTab('chat');
      send('请解释我选中的这段内容：\n\n> ' + sel.replace(/\n/g, '\n> '), {});
    });

    window.addEventListener('scroll', hideChip, true);
  }

  function hideChip() {
    if (CP.el.chip) CP.el.chip.hidden = true;
  }

  /* ------------------------------------------------------------------
     设置对话框
     ------------------------------------------------------------------ */
  function openSettings() {
    var m = CP.el.modal;
    if (!m) return;
    m.hidden = false;
    loadConfigIntoForm();
  }
  function closeSettings() {
    if (CP.el.modal) CP.el.modal.hidden = true;
    if (CP.el.testOut) CP.el.testOut.textContent = '';
  }

  function loadConfigIntoForm() {
    fetch('/api/ai/config').then(function (r) { return r.json(); }).then(function (c) {
      CP.cfg = c;
      var sel = CP.el.preset;
      if (sel) {
        sel.innerHTML = Object.keys(CP.presets).map(function (k) {
          var p = CP.presets[k];
          return '<option value="' + esc(k) + '"' + (c.preset === k ? ' selected' : '') + '>' + esc(p.name) + '</option>';
        }).join('');
      }
      if (CP.el.baseUrl) CP.el.baseUrl.value = c.base_url || '';
      if (CP.el.model) CP.el.model.value = c.model || '';
      if (CP.el.key) {
        CP.el.key.value = '';
        CP.el.key.placeholder = c.key_masked ? ('已保存：' + c.key_masked + '（留空则不修改）') : 'sk-...';
      }
      if (CP.el.temp) {
        CP.el.temp.value = c.temperature;
        CP.el.tempVal.textContent = Number(c.temperature).toFixed(1);
      }
    }).catch(function () {
      if (CP.el.testOut) CP.el.testOut.textContent = '读取配置失败';
    });
  }

  function saveSettings() {
    var body = {
      preset: CP.el.preset ? CP.el.preset.value : undefined,
      base_url: CP.el.baseUrl ? CP.el.baseUrl.value.trim() : undefined,
      model: CP.el.model ? CP.el.model.value.trim() : undefined,
      temperature: CP.el.temp ? Number(CP.el.temp.value) : undefined
    };
    var k = CP.el.key ? CP.el.key.value.trim() : '';
    if (k) body.api_key = k;

    fetch('/api/ai/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); }).then(function (c) {
      CP.cfg = c;
      closeSettings();
      toast(c.configured ? '已保存' : '已保存，但还没配置密钥');
    }).catch(function () { toast('保存失败'); });
  }

  function testConn() {
    var out = CP.el.testOut;
    if (out) out.textContent = '正在测试…';
    var body = {
      base_url: CP.el.baseUrl ? CP.el.baseUrl.value.trim() : '',
      model: CP.el.model ? CP.el.model.value.trim() : ''
    };
    var k = CP.el.key ? CP.el.key.value.trim() : '';
    if (k) body.api_key = k;
    fetch('/api/ai/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); }).then(function (o) {
      if (o.ok) {
        out.textContent = '✅ 连通（' + o.ms + 'ms）· ' + (o.reply || '').replace(/\n/g, ' ');
        out.className = 'cp-test-out ok';
      } else {
        out.textContent = '❌ ' + (o.error || '失败');
        out.className = 'cp-test-out bad';
      }
    }).catch(function (e) {
      out.textContent = '❌ ' + e.message;
      out.className = 'cp-test-out bad';
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
      msgs:     $('#cpMsgs'),
      quick:    $('#cpQuick'),
      input:    $('#cpInput'),
      send:     $('#cpSend'),
      typing:   $('#cpTyping'),
      chip:     $('#cpSelChip'),
      modal:    $('#cpModal'),
      preset:   $('#cpPreset'),
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

    // 预设表
    fetch('/api/ai/presets').then(function (r) { return r.json(); }).then(function (o) {
      CP.presets = o.presets || {};
      if (CP.el.preset) {
        CP.el.preset.innerHTML = Object.keys(CP.presets).map(function (k) {
          return '<option value="' + esc(k) + '">' + esc(CP.presets[k].name) + '</option>';
        }).join('');
      }
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
      if (saveBtn) saveBtn.addEventListener('click', saveSettings);
      var testBtn = $('#cpTest');
      if (testBtn) testBtn.addEventListener('click', testConn);
      CP.el.modal.addEventListener('click', function (ev) {
        if (ev.target === CP.el.modal) closeSettings();
      });
      if (CP.el.preset) {
        CP.el.preset.addEventListener('change', function () {
          var p = CP.presets[CP.el.preset.value];
          if (!p) return;
          CP.el.baseUrl.value = p.base_url;
          CP.el.model.value = p.model;
        });
      }
      if (CP.el.temp) {
        CP.el.temp.addEventListener('input', function () {
          CP.el.tempVal.textContent = Number(CP.el.temp.value).toFixed(1);
        });
      }
    }

    // 选中冒泡
    initSelectionChip();

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
