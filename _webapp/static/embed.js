/* 嵌入模式（?embed=1）：给 DSH 学习台的 iframe 用。
 *
 * 只做两件事：
 *   1. 关掉我们自己的「AI 陪读」——嵌入时唯一的 AI 入口是 DSH 的对话；
 *   2. 把「当前文件 + 选中文字」用 postMessage 发给宿主插件，
 *      插件再把它拼成一条消息发进对话（这是我们和宿主之间的私有协议）。
 *
 * 独立打开（不带 ?embed=1）时本文件什么都不做。顶栏不动。
 */
(function () {
  'use strict';

  var params = new URLSearchParams(location.search || '');
  if (!params.has('embed')) return;

  document.documentElement.dataset.embed = '1';

  var MAX_SELECTION = 2000;
  var lastSent = { path: null, selection: '', at: 0 };
  var timer = null;

  function currentPath() {
    var hash = String(location.hash || '');
    if (!hash) return '';
    var raw = hash.replace(/^#/, '').replace(/^\//, '').split('?')[0];
    try { return decodeURIComponent(raw); } catch (e) { return raw; }
  }

  function currentTitle() {
    var selectors = ['#doc .doc-title', '#doc h1', '.doc-head h1', '.doc-title', '#docTitle', '#doc h2'];
    for (var i = 0; i < selectors.length; i += 1) {
      var el = document.querySelector(selectors[i]);
      if (el && el.textContent && el.textContent.trim()) return el.textContent.trim().slice(0, 120);
    }
    return String(document.title || '').trim().slice(0, 120);
  }

  function selectionText() {
    try {
      var sel = window.getSelection ? window.getSelection() : null;
      var text = sel ? String(sel).trim() : '';
      return text.length > MAX_SELECTION ? text.slice(0, MAX_SELECTION) : text;
    } catch (e) { return ''; }
  }

  /* 让陪读退场：关面板、摘按钮、把开关变成空操作。
     不删代码——独立模式（不带 embed）还要用它。 */
  function silenceCompanion() {
    var panel = document.getElementById('companion');
    if (panel && !panel.hidden) {
      try {
        if (window.Companion && typeof window.Companion.toggle === 'function') window.Companion.toggle();
        else panel.hidden = true;
      } catch (e) { panel.hidden = true; }
    }
    if (document.body.classList.contains('cp-open')) document.body.classList.remove('cp-open');

    if (window.Companion && !window.Companion.__embedMuted) {
      window.Companion.toggle = function () { /* 嵌入模式下不启用：AI 入口交给宿主对话 */ };
      window.Companion.__embedMuted = true;
    }

    var btn = document.getElementById('btnCompanion');
    if (btn && btn.parentNode) btn.parentNode.removeChild(btn);
  }

  function push(force) {
    if (window.parent === window) return;
    var path = currentPath();
    var selection = selectionText();
    var now = Date.now();
    if (!force && path === lastSent.path && selection === lastSent.selection && now - lastSent.at < 1500) return;
    lastSent = { path: path, selection: selection, at: now };
    try {
      window.parent.postMessage({
        source: 'studyhub',
        type: 'context',
        path: path,
        title: currentTitle(),
        selection: selection,
        href: location.href,
        at: new Date().toISOString()
      }, '*');
    } catch (e) { /* 宿主不在就算了 */ }
  }

  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(function () { push(false); }, 350);
  }

  /* 临时提示条：发给宿主之后给用户一个"收到了"的信号 */
  var toastEl = null;
  var toastTimer = null;
  function toast(text) {
    try {
      if (!toastEl) {
        toastEl = document.createElement('div');
        toastEl.style.cssText = [
          'position:fixed', 'left:50%', 'bottom:28px', 'transform:translateX(-50%)',
          'padding:8px 14px', 'border-radius:999px', 'font-size:13px', 'z-index:99999',
          'background:rgba(20,20,20,.86)', 'color:#fff', 'pointer-events:none',
          'transition:opacity .2s', 'max-width:80vw', 'white-space:nowrap',
          'overflow:hidden', 'text-overflow:ellipsis', 'box-shadow:0 6px 20px rgba(0,0,0,.28)'
        ].join(';');
        document.body.appendChild(toastEl);
      }
      toastEl.textContent = text;
      toastEl.style.opacity = '1';
      clearTimeout(toastTimer);
      toastTimer = setTimeout(function () { if (toastEl) toastEl.style.opacity = '0'; }, 2400);
    } catch (e) { /* 提示失败不影响功能 */ }
  }

  /** 把"我选了这段，问一下"交给宿主：由 DSH 的对话来回答，不用我们自己的 Key。 */
  function ask(selection) {
    var text = String(selection || '').trim();
    if (!text) return false;
    if (window.parent === window) return false;
    try {
      window.parent.postMessage({
        source: 'studyhub',
        type: 'ask',
        path: currentPath(),
        title: currentTitle(),
        selection: text,
        href: location.href,
        at: new Date().toISOString()
      }, '*');
      toast('已发给 DSH 对话…');
      return true;
    } catch (e) {
      return false;
    }
  }

  /* 宿主发回的结果（成功/失败原因），给用户看 */
  window.addEventListener('message', function (event) {
    var data = event && event.data;
    if (!data || data.source !== 'dsh' || data.type !== 'ask-ack') return;
    toast(data.ok ? '已发进 DSH 对话' : ('发送失败：' + String(data.message || '')));
  });

  function boot() {
    document.body.classList.add('embed');
    silenceCompanion();
    push(true);

    window.addEventListener('hashchange', function () { push(true); });
    document.addEventListener('selectionchange', schedule);
    document.addEventListener('mouseup', schedule);
    document.addEventListener('keyup', schedule);
    // 正文是异步渲染的，标题/内容晚一拍才稳
    setTimeout(function () { push(true); }, 900);

    window.__studyhubEmbed = {
      get context() { return { path: currentPath(), title: currentTitle(), selection: selectionText() }; },
      push: function () { push(true); },
      ask: ask
    };
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
