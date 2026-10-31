/* =====================================================================
   我的书库 —— 浏览用户自己放进来的资料

   隔离说明
     · 只用 /api/library/* 和已有的 /api/file、/api/raw
     · 不引用 app.js / companion.js，完全不碰主界面逻辑
     · 渲染复用 Renderers（和主阅读器同一套）
   ===================================================================== */
(function () {
  'use strict';

  var main = document.getElementById('main');
  var statEl = document.getElementById('stat');
  var btnReveal = document.getElementById('btnReveal');

  var DIRNAME = '书库';      // 书库目录名，由 /api/library/info 返回（可配置）
  var CUR_DIR = '';          // 当前目录（相对书库根）
  var READING = null;        // 正在读的文件路径，null 表示列表视图

  var ICONS = {
    markdown: '📝', notebook: '📓', pdf: '📕', image: '🖼️',
    html: '🌐', code: '💻', text: '📄', binary: '📦', unknown: '❓'
  };

  /* ---------- 工具 ---------- */
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function human(n) {
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
    return (n / 1048576).toFixed(1) + ' MB';
  }
  function getJSON(url) {
    return fetch(url, { cache: 'no-store' }).then(function (r) {
      if (!r.ok) return r.text().then(function (t) { throw new Error(t || ('HTTP ' + r.status)); });
      return r.json();
    });
  }

  /* ---------- 顶栏统计 ---------- */
  function loadStats() {
    getJSON('/api/library/info').then(function (s) {
      if (s.dirName) DIRNAME = s.dirName;
      statEl.textContent = s.files
        ? (s.files + ' 个文件 · ' + human(s.bytes))
        : '还是空的';
    }).catch(function () { statEl.textContent = ''; });
  }

  /* ---------- 面包屑 ---------- */
  function crumbHTML(dir) {
    var parts = dir ? dir.split('/') : [];
    var out = ['<a data-dir="">书库</a>'];
    var acc = '';
    parts.forEach(function (p) {
      acc = acc ? acc + '/' + p : p;
      out.push('<span>/</span><a data-dir="' + esc(acc) + '">' + esc(p) + '</a>');
    });
    return '<div class="crumb">' + out.join('') + '</div>';
  }

  /* ---------- 列表 ---------- */
  function renderList(data) {
    READING = null;
    var html = crumbHTML(data.path || '');
    var dirs = data.dirs || [], files = data.files || [];

    if (!dirs.length && !files.length) {
      html += '<div class="empty">' +
        '<div class="big">📚</div>' +
        '<p>这里还没有资料</p>' +
        '<p style="font-size:13px">点右上角「打开文件夹」，把你的 Markdown / PDF / 图片放进去，刷新就行</p>' +
        '</div>';
      main.innerHTML = html;
      return;
    }

    html += '<div class="grid">';
    dirs.forEach(function (d) {
      html += '<div class="card" data-dir="' + esc(d.path) + '">' +
        '<div class="ico">📁</div>' +
        '<div class="nm">' + esc(d.name) + '</div>' +
        '<div class="mt">文件夹</div></div>';
    });
    files.forEach(function (f) {
      var icon = ICONS[f.kind] || '📄';
      html += '<div class="card" data-file="' + esc(f.path) + '">' +
        '<div class="ico">' + icon + '</div>' +
        '<div class="nm">' + esc(f.name) + '</div>' +
        '<div class="mt">' + human(f.size) + (f.renderable ? '' : ' · 不支持预览') + '</div></div>';
    });
    html += '</div>';
    main.innerHTML = html;
  }

  function loadDir(dir) {
    CUR_DIR = dir || '';
    if (location.hash) history.replaceState(null, '', location.pathname);
    main.innerHTML = '<div class="loading">加载中…</div>';
    getJSON('/api/library/list?path=' + encodeURIComponent(CUR_DIR))
      .then(renderList)
      .catch(function (e) {
        main.innerHTML = '<div class="empty"><div class="big">⚠️</div><p>' + esc(e.message) + '</p></div>';
      });
  }
  /* ---------- 读文件 ---------- */
  function openFile(path) {
    READING = path;
    if (location.hash !== '#/' + path) location.hash = '#/' + path;
    main.innerHTML = '<div class="loading">打开中…</div>';

    // 列表返回的是「书库内相对路径」，而 /api/file 按资料根目录解析，所以要补上 书库/ 前缀
    var fullPath = DIRNAME + '/' + path;
    getJSON('/api/file?path=' + encodeURIComponent(fullPath))
      .then(function (file) {
        var dir = path.split('/').slice(0, -1).join('/');
        var html = crumbHTML(dir) +
          '<div class="crumb" style="margin-top:-10px"><a data-back="1">← 返回列表</a>' +
          '<span style="color:var(--dim)">·</span><span>' + esc(file.name) + '</span></div>';

        var out;
        try {
          out = window.Renderers.render(file);
        } catch (e) {
          out = { html: '<p style="color:#ef4444">渲染失败：' + esc(e.message) + '</p>' };
        }
        html += '<div class="reader">' + out.html + '</div>';
        main.innerHTML = html;

        // 让代码高亮和公式生效（和主阅读器同一套后处理）
        try {
          if (window.Renderers.postProcess) window.Renderers.postProcess(main);
        } catch (e) {}
      })
      .catch(function (e) {
        main.innerHTML = '<div class="empty"><div class="big">⚠️</div><p>' + esc(e.message) + '</p></div>';
      });
  }

  /* ---------- 事件（全部用委托，避免重复绑定） ---------- */
  /* ---------- 事件（全部用委托，避免重复绑定） ---------- */
  main.addEventListener('click', function (ev) {
    var t = ev.target.closest('[data-dir],[data-file],[data-back]');
    if (!t) return;
    if (t.hasAttribute('data-back')) {
      loadDir(CUR_DIR);
    } else if (t.hasAttribute('data-dir')) {
      loadDir(t.getAttribute('data-dir'));
    } else if (t.hasAttribute('data-file')) {
      openFile(t.getAttribute('data-file'));
    }
  });
  btnReveal.addEventListener('click', function () {
    btnReveal.disabled = true;
    fetch('/api/library/reveal?path=' + encodeURIComponent(CUR_DIR), { method: 'GET' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok) {
          btnReveal.textContent = '✅ 已打开';
          setTimeout(function () { btnReveal.textContent = '📂 打开文件夹'; }, 1600);
        } else {
          alert(d.error || '打开失败');
        }
      })
      .catch(function (e) { alert('打开失败：' + e.message); })
      .finally(function () { btnReveal.disabled = false; });
  });

  /* ---------- 提示条 ---------- */
  var toastEl = null, toastTimer = null;
  function toast(msg, bad) {
    if (!toastEl) {
      toastEl = document.createElement('div');
      toastEl.className = 'toast';
      document.body.appendChild(toastEl);
    }
    toastEl.textContent = msg;
    toastEl.className = 'toast show' + (bad ? ' bad' : '');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.className = 'toast'; }, 2200);
  }

  /* ---------- 右键菜单（类比 VSCode 的 Open With）---------- */
  var menuEl = null;
  function closeMenu() { if (menuEl) { menuEl.remove(); menuEl = null; } }

  function showMenu(x, y, items) {
    closeMenu();
    var el = document.createElement('div');
    el.className = 'ctx';
    items.forEach(function (it) {
      if (it.sep) { var s = document.createElement('div'); s.className = 'ctx-sep'; el.appendChild(s); return; }
      var d = document.createElement('div');
      d.className = 'ctx-item';
      d.innerHTML = '<span class="ci">' + (it.icon || '') + '</span><span>' + esc(it.label) + '</span>';
      if (it.run) d.addEventListener('click', function (ev) { ev.stopPropagation(); closeMenu(); it.run(); });
      el.appendChild(d);
    });
    document.body.appendChild(el);
    menuEl = el;
    var r = el.getBoundingClientRect();
    el.style.left = Math.max(6, Math.min(x, window.innerWidth - r.width - 8)) + 'px';
    el.style.top = Math.max(6, Math.min(y, window.innerHeight - r.height - 8)) + 'px';
  }

  document.addEventListener('click', closeMenu);
  document.addEventListener('scroll', closeMenu, true);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeMenu(); });

  function copyText(s) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(s).then(function () { toast('路径已复制'); },
        function () { toast('复制失败', true); });
    } else {
      toast('浏览器不支持剪贴板', true);
    }
  }

  function openWith(path, appId, label) {
    getJSON('/api/library/open?path=' + encodeURIComponent(path) +
            '&app=' + encodeURIComponent(appId))
      .then(function () { toast(label || '已打开'); })
      .catch(function (e) { toast(e.message || '打开失败', true); });
  }

  main.addEventListener('contextmenu', function (ev) {
    var card = ev.target.closest('[data-file],[data-dir]');
    if (!card) return;
    ev.preventDefault();

    var x = ev.clientX, y = ev.clientY;
    var isFile = card.hasAttribute('data-file');
    var path = isFile ? card.getAttribute('data-file') : card.getAttribute('data-dir');

    if (!isFile) {
      showMenu(x, y, [
        { icon: '📂', label: '在资源管理器中打开', run: function () {
            getJSON('/api/library/open?path=' + encodeURIComponent(path) + '&app=explorer')
              .then(function () { toast('已打开'); }).catch(function (e) { toast(e.message, true); });
        } },
        { sep: true },
        { icon: '📋', label: '复制路径', run: function () { copyText(DIRNAME + '/' + path); } }
      ]);
      return;
    }

    // 文件：先拉「这台机器上真正可用的打开方式」，再弹菜单
    getJSON('/api/library/apps?path=' + encodeURIComponent(path))
      .then(function (d) {
        var items = [
          { icon: '📖', label: '在阅读器里打开', run: function () { openFile(path); } },
          { sep: true }
        ];
        (d.apps || []).forEach(function (a) {
          items.push({
            icon: a.icon, label: a.label,
            run: function () { openWith(path, a.id, a.label.replace('打开', '已用') + ''); }
          });
        });
        items.push({ sep: true });
        items.push({ icon: '📋', label: '复制路径', run: function () { copyText(DIRNAME + '/' + path); } });
        showMenu(x, y, items);
      })
      .catch(function () {
        // 兜底：至少能读、能复制
        showMenu(x, y, [
          { icon: '📖', label: '在阅读器里打开', run: function () { openFile(path); } },
          { sep: true },
          { icon: '📋', label: '复制路径', run: function () { copyText(DIRNAME + '/' + path); } }
        ]);
      });
  });

  /* ---------- 启动 ---------- */
  loadStats();
  var startFile = location.hash.replace(/^#\/?/, '');
  if (startFile) {
    try { openFile(decodeURIComponent(startFile)); } catch (e) { loadDir(''); }
  } else {
    loadDir('');
  }

  // 浏览器前进 / 后退
  window.addEventListener('hashchange', function () {
    var p = '';
    try { p = decodeURIComponent(location.hash.replace(/^#\/?/, '')); } catch (e) {}
    if (p && p !== READING) openFile(p);
    else if (!p && READING) loadDir(CUR_DIR);
  });
})();
