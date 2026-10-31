/* =====================================================================
   临时预览提示条

   场景：从资源管理器右键一个「不在书库目录里」的文件时，它会被放进
   书库\.preview\<随机>\ 里直接打开 —— 先让你看，不打扰。

   这条提示就负责最后那一步：看完要留还是不留。
     · 点「保存到书库」 → 移到 书库\导入\
     · 点「丢弃」       → 立刻删掉
     · 什么都不点直接关 → 服务退出时静默删掉（等于不导入）

   独立文件，不改 app.js，靠 location.hash 判断当前打开的是不是预览文件。
   ===================================================================== */
(function () {
  'use strict';

  var LIB_NAME = '书库';
  var BAR_ID = 'pvBar';

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function currentPath() {
    var h = location.hash || '';
    if (h.indexOf('#/') !== 0) return '';
    try { return decodeURIComponent(h.slice(2)); } catch (e) { return ''; }
  }

  function isPreview(path) {
    var pre = LIB_NAME + '/.preview/';
    return path.indexOf(pre) === 0;
  }

  // ROOT 相对路径 → 书库相对路径（接口要的是后者）
  function libRel(path) {
    var pre = LIB_NAME + '/';
    return path.indexOf(pre) === 0 ? path.slice(pre.length) : path;
  }

  function remove() {
    var el = document.getElementById(BAR_ID);
    if (el) el.remove();
  }

  function say(msg, bad) {
    var el = document.createElement('div');
    el.className = 'pv-toast' + (bad ? ' bad' : '');
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function () { el.classList.add('show'); }, 10);
    setTimeout(function () {
      el.classList.remove('show');
      setTimeout(function () { el.remove(); }, 250);
    }, 2200);
  }

  function call(api, path) {
    return fetch(api + '?path=' + encodeURIComponent(libRel(path)))
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.d.error || res.d.message || '操作失败');
        return res.d;
      });
  }

  function show(path) {
    remove();

    var bar = document.createElement('div');
    bar.id = BAR_ID;
    bar.className = 'pvbar';
    bar.innerHTML =
      '<span class="pv-ico">📥</span>' +
      '<span class="pv-txt">临时预览 · 不保存关掉就没了</span>' +
      '<button class="pv-btn primary" data-act="save">保存到书库</button>' +
      '<button class="pv-btn" data-act="drop">丢弃</button>';

    bar.addEventListener('click', function (ev) {
      var btn = ev.target.closest('button[data-act]');
      if (!btn) return;
      var act = btn.getAttribute('data-act');
      var isSave = act === 'save';

      btn.disabled = true;
      call(isSave ? '/api/library/promote' : '/api/library/discard', path)
        .then(function (d) {
          remove();
          if (isSave) {
            say('已保存到 书库\\导入\\' + (d.name ? '（' + d.name + '）' : ''));
            location.hash = '#/' + encodeURI(LIB_NAME + '/导入/' + d.name);
          } else {
            say('已丢弃');
            location.hash = '#/';
          }
        })
        .catch(function (e) {
          btn.disabled = false;
          say(e.message, true);
        });
    });

    document.body.appendChild(bar);
  }

  function sync() {
    var p = currentPath();
    if (p && isPreview(p)) show(p);
    else remove();
  }

  window.addEventListener('hashchange', sync);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', sync);
  } else {
    setTimeout(sync, 60);
  }
})();
