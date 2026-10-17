/* =====================================================================
   agent学习平台 · 主应用
   ===================================================================== */
(function () {
  'use strict';

  var R = window.Renderers;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  var LS = {
    theme: 'studyai.theme',
    recent: 'studyai.recent',
    read: 'studyai.read',
    sidebar: 'studyai.sidebar',
    toc: 'studyai.toc'
  };

  var state = {
    treeCache: {},        // path -> {dirs, files}
    expanded: {},         // path -> bool
    current: null,        // 当前文件对象
    filter: '',
    readSet: {},
    recent: [],
    stats: null,
    readTimer: null,
    tocObserver: null
  };

  /* ================= 本地存储 ================= */
  function lsGet(k, dflt) {
    try { var v = localStorage.getItem(k); return v == null ? dflt : JSON.parse(v); }
    catch (e) { return dflt; }
  }
  function lsSet(k, v) {
    try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {}
  }

  /* ================= 提示 / 加载条 ================= */
  var toastTimer;
  function toast(msg) {
    var el = $('#toast');
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.classList.remove('show'); }, 1900);
  }

  var barTimer;
  function loading(on) {
    var el = $('#loadingBar');
    if (on) {
      el.classList.add('on');
      el.style.width = '15%';
      var w = 15;
      clearInterval(barTimer);
      barTimer = setInterval(function () {
        w = Math.min(w + (90 - w) * 0.12, 90);
        el.style.width = w + '%';
      }, 180);
    } else {
      clearInterval(barTimer);
      el.style.width = '100%';
      setTimeout(function () { el.classList.remove('on'); el.style.width = '0'; }, 260);
    }
  }

  /* ================= API ================= */
  function api(path, params) {
    var qs = Object.keys(params || {}).map(function (k) {
      return k + '=' + encodeURIComponent(params[k]);
    }).join('&');
    return fetch(path + (qs ? '?' + qs : '')).then(function (r) {
      if (!r.ok) return r.json().then(function (j) { throw new Error(j.error || ('HTTP ' + r.status)); });
      return r.json();
    });
  }

  /* ================= 文件图标 ================= */
  var ICONS = {
    markdown: '📄', notebook: '📓', code: '📜', text: '📃',
    pdf: '📕', image: '🖼', html: '🌐', binary: '📦', unknown: '❔', dir: '📁'
  };
  function iconFor(node) {
    if (node.type === 'dir') return ICONS.dir;
    return ICONS[node.kind] || ICONS.unknown;
  }

  /* 统一课程图标（目录树里每个章节前面的那张图）
     换图标只需要改这一个路径，图片替换到 _webapp/static/ 下即可。 */
  var ICON_LESSON = '/static/fish-22.png';

  /* ---------- 目录树：友好的显示名 ---------- */

  /* 阿拉伯数字 -> 中文序数（1 一 … 99 九十九） */
  function cnNum(n) {
    var D = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九'];
    if (n <= 0) return String(n);
    if (n < 10) return D[n];
    if (n === 10) return '十';
    if (n < 20) return '十' + D[n - 10];
    if (n < 100) {
      var t = Math.floor(n / 10), r = n % 10;
      return D[t] + '十' + (r ? D[r] : '');
    }
    return String(n);
  }

  /* chapter_19_workflow_patterns -> { seq:20, title:'Agentic Workflow 设计模式' }
     标题取自 roadmap.js，是课程里的中文正式名 */
  var _chapMap = null;
  function chapterMap() {
    if (_chapMap) return _chapMap;
    _chapMap = {};
    var RM = window.ROADMAP || {};
    (RM.stages || []).forEach(function (st) {
      (st.items || []).forEach(function (it) {
        var m = String(it.path || '').match(/(chapter_(\d+)_[^/]+)\//);
        if (!m) return;
        _chapMap[m[1]] = { seq: parseInt(m[2], 10) + 1, title: it.title, no: it.no };
      });
    });
    return _chapMap;
  }

  /* 这些是工程文件，不是学习内容 —— 默认收起来 */
  var HIDE_NAMES = {
    'README.md': 1, 'README-课程原版.md': 1, 'LICENSE': 1,
    'THIRD-PARTY-NOTICES.md': 1, '.gitignore': 1, '.gitattributes': 1,
    'setup.ps1': 1, 'requirements.txt': 1, 'pyproject.toml': 1,
    'package.json': 1, 'package-lock.json': 1, 'docs': 1, '.github': 1
  };

  function isHidden(node) {
    if (state.showAllFiles) return false;
    return !!HIDE_NAMES[node.name];
  }

  function filterNodes(list) {
    return (list || []).filter(function (n) { return !isHidden(n); });
  }

  /* 覆盖显示名；返回 null 表示按原名显示 */
  function displayOverride(node) {
    var cm = chapterMap();

    // 章节文件夹：第N节 + 中文标题
    if (node.type === 'dir' && cm[node.name]) {
      return { cls: 'is-lesson', badge: cnNum(cm[node.name].seq), label: cm[node.name].title };
    }

    // 根目录：去掉 01- 这种排序前缀
    if (node.type === 'dir' && node.path.indexOf('/') < 0) {
      var clean = node.name.replace(/^\d+[-_]/, '');
      if (clean !== node.name) return { cls: 'is-root', badge: '', label: clean };
    }

    // 章节里的文件：讲义 / Python 源码
    if (node.type === 'file') {
      var parts = node.path.split('/');
      var parent = parts[parts.length - 2];
      if (parent && cm[parent]) {
        if (/\.html?$/i.test(node.name))   return { cls: 'is-file', badge: '', label: '讲义', kind: 'html' };
        if (/\.py$/i.test(node.name))      return { cls: 'is-file', badge: '', label: 'Python 源码', kind: 'py' };
      }
    }
    return null;
  }

  /* =================================================================
     文件树
     ================================================================= */
  function makeRow(node, depth) {
    var ov = displayOverride(node);

    var row = document.createElement('div');
    row.className = 'trow' + (ov ? ' ' + ov.cls : '');
    row.dataset.path = node.path;
    row.dataset.type = node.type;
    if (ov && ov.kind) row.dataset.kind = ov.kind;
    row.style.paddingLeft = (6 + depth * 12) + 'px';

    var arrow = document.createElement('span');
    arrow.className = 'tarrow' + (node.type === 'file' ? ' leaf' : '');
    arrow.textContent = '▶';
    row.appendChild(arrow);

    if (ov && ov.badge) {
      // 章节行：大肥鱼图标 + 序号徽章
      // 想换图标就改 ICON_LESSON 的路径（建议 22~32px 见方的 PNG）
      var fish = document.createElement('img');
      fish.className = 'tfish';
      fish.src = ICON_LESSON;
      fish.alt = '';
      fish.loading = 'lazy';
      row.appendChild(fish);

      var badge = document.createElement('span');
      badge.className = 'tbadge';
      badge.textContent = ov.badge;
      row.appendChild(badge);
    } else if (ov && ov.kind) {
      var dot = document.createElement('span');
      dot.className = 'tdot';
      row.appendChild(dot);
    } else {
      var ico = document.createElement('span');
      ico.className = 'tico';
      ico.textContent = iconFor(node);
      row.appendChild(ico);
    }

    var name = document.createElement('span');
    name.className = 'tname';
    name.textContent = ov ? ov.label : node.name;
    name.title = ov ? (ov.label + '\n' + node.path) : node.path;
    row.appendChild(name);

    // 章节序号已在徽章里，尺寸对讲义无意义，只在非章节文件上显示
    if (node.type === 'file' && node.size != null && !(ov && ov.kind)) {
      var sz = document.createElement('span');
      sz.className = 'tsize';
      sz.textContent = R.humanSize(node.size);
      row.appendChild(sz);
    }

    if (node.type === 'file' && !node.renderable) {
      row.classList.add('unrenderable');
      row.title = node.path + '\n（此类型无法在网页中查看）';
    }
    if (node.type === 'file' && state.readSet[node.path]) row.classList.add('read');

    return row;
  }

  function renderNodes(container, nodes, depth) {
    nodes.forEach(function (n) {
      var wrap = document.createElement('div');
      wrap.className = 'tnode';
      var row = makeRow(n, depth);
      wrap.appendChild(row);

      if (n.type === 'dir') {
        var kids = document.createElement('div');
        kids.className = 'tchildren';
        kids.hidden = true;
        kids.dataset.loaded = '0';
        kids.dataset.path = n.path;
        wrap.appendChild(kids);
      }
      container.appendChild(wrap);
    });
  }

  function loadTree(path, container, depth) {
    if (state.treeCache[path]) {
      fillChildren(path, container, depth);
      return Promise.resolve();
    }
    return api('/api/tree', { path: path }).then(function (data) {
      state.treeCache[path] = data;
      fillChildren(path, container, depth);
    }).catch(function (e) {
      container.innerHTML = '<div class="tree-loading">加载失败: ' + R.esc(e.message) + '</div>';
    });
  }

  function fillChildren(path, container, depth) {
    var data = state.treeCache[path];
    container.innerHTML = '';
    var all = filterNodes((data.dirs || []).concat(data.files || []));
    if (!all.length) {
      container.innerHTML = '<div class="tree-loading">（空目录）</div>';
      return;
    }
    renderNodes(container, all, depth);
    container.dataset.loaded = '1';
    applyFilter(container);
  }

  function toggleDir(row, kids, path, depth) {
    var open = !state.expanded[path];
    state.expanded[path] = open;
    row.querySelector('.tarrow').classList.toggle('open', open);
    kids.hidden = !open;
    if (open && kids.dataset.loaded === '0') {
      loadTree(path, kids, depth + 1);
    }
  }

  function expandTo(path, cb) {
    var parts = path.split('/');
    var acc = '';
    var chain = [];
    for (var i = 0; i < parts.length - 1; i++) {
      acc = acc ? acc + '/' + parts[i] : parts[i];
      chain.push(acc);
    }
    var i = 0;
    function step() {
      if (i >= chain.length) { cb && cb(); return; }
      var p = chain[i++];
      state.expanded[p] = true;
      var node = document.querySelector('.tchildren[data-path="' + cssEsc(p) + '"]');
      if (!node) { cb && cb(); return; }
      var row = node.parentElement.querySelector('.trow');
      if (row) row.querySelector('.tarrow').classList.add('open');
      node.hidden = false;
      var load = node.dataset.loaded === '0'
        ? loadTree(p, node, p.split('/').length)
        : Promise.resolve();
      load.then(function () { setTimeout(step, 16); });
    }
    step();
  }

  function cssEsc(s) { return String(s).replace(/["\\]/g, '\\$&'); }

  function initTree() {
    var tree = $('#tree');
    return api('/api/tree', { path: '' }).then(function (data) {
      state.treeCache[''] = data;
      tree.innerHTML = '';
      var all = filterNodes((data.dirs || []).concat(data.files || []));
      renderNodes(tree, all, 0);
    }).catch(function (e) {
      tree.innerHTML = '<div class="tree-loading">加载失败: ' + R.esc(e.message) + '</div>';
    });
  }

  /* 树事件委托 */
  function bindTree() {
    $('#tree').addEventListener('click', function (ev) {
      var row = ev.target.closest('.trow');
      if (!row) return;
      var path = row.dataset.path;
      var type = row.dataset.type;

      if (type === 'dir') {
        var kids = row.nextElementSibling;
        if (kids && kids.classList.contains('tchildren')) {
          toggleDir(row, kids, path, path.split('/').length);
        }
      } else {
        if (row.classList.contains('unrenderable')) {
          copyText(path);
          toast('该类型无法在网页查看，路径已复制');
          return;
        }
        location.hash = '#/' + encodeURI(path);
      }
    });
  }

  /* 过滤 */
  function applyFilter(scope) {
    var q = state.filter.trim().toLowerCase();
    $$('.trow', scope || document).forEach(function (row) {
      if (!q) { row.style.display = ''; return; }
      var name = row.querySelector('.tname').textContent.toLowerCase();
      var isDir = row.dataset.type === 'dir';
      row.style.display = (isDir || name.indexOf(q) >= 0) ? '' : 'none';
    });
    if (!q) return;
    // 有匹配文件的目录自动展开
    $$('.tnode', scope || document).forEach(function (node) {
      var kids = node.querySelector(':scope > .tchildren');
      if (!kids) return;
      var hit = $$('.trow', kids).some(function (r) {
        return r.style.display !== 'none' && r.dataset.type === 'file';
      });
      if (hit) {
        kids.hidden = false;
        var row = node.querySelector(':scope > .trow');
        if (row) row.querySelector('.tarrow').classList.add('open');
      }
    });
  }

  /* =================================================================
     内容加载
     ================================================================= */
  function parseHash() {
    var h = location.hash || '';
    if (h.indexOf('#/') !== 0) return null;
    var raw = h.slice(2);
    if (!raw) return null;
    try { return decodeURI(raw); } catch (e) { return raw; }
  }

  function openFile(path, opts) {
    opts = opts || {};
    loading(true);
    return api('/api/file', { path: path }).then(function (file) {
      state.current = file;
      renderFile(file);
      addRecent(file);
      setCrumbs(file.path);
      markActiveInTree(file.path);
      startReadTimer(file);
      if (!opts.noHash) {
        var want = '#/' + encodeURI(file.path);
        if (location.hash !== want) {
          history.replaceState(null, '', want);
        }
      }
      document.title = file.name + ' · agent学习平台';
      // 通知陪读面板：换章节了
      if (window.Companion) window.Companion.updateContext(file);
      loading(false);
    }).catch(function (e) {
      loading(false);
      showError(e.message, path);
    });
  }

  function renderFile(file) {
    var doc = $('#doc');
    var welcome = $('#welcome');
    welcome.hidden = true;
    doc.hidden = false;
    doc.scrollTop = 0;
    $('#content').scrollTop = 0;

    var result;
    try {
      result = R.render(file);
    } catch (e) {
      showError('渲染失败: ' + e.message, file.path);
      return;
    }

    // HTML 用 iframe 承载，需要占满可用空间 —— 860px 的阅读宽度会把它挤得很小
    var wide = (file.kind === 'html');
    doc.classList.toggle('doc--wide', wide);

    var head = '<div class="doc-head"><div class="dh-main">' +
      '<h1>' + R.esc(file.name) + '</h1>' +
      '<div class="doc-meta">' +
        '<span>' + R.esc(file.path) + '</span>' +
        '<span>' + R.humanSize(file.size) + '</span>' +
        '<span>' + kindLabel(file) + '</span>' +
        (file.encoding && file.encoding !== 'utf-8' ? '<span>编码 ' + file.encoding + '</span>' : '') +
      '</div></div>' +
      '<div class="doc-actions">' +
        '<button class="icon-btn" id="btnRead" title="标记已读/未读">' +
          (state.readSet[file.path] ? '✅' : '⬜') + '</button>' +
        '<button class="icon-btn" id="btnCopyPath" title="复制路径">📋</button>' +
        (wide ? '<button class="icon-btn" id="btnOpenTab" title="在新标签页打开（可全屏，支持页面内导航）">↗</button>' : '') +
      '</div></div>';

    doc.innerHTML = head + result.html;
    R.postProcess(doc);

    // 按钮
    var br = $('#btnRead', doc);
    if (br) br.addEventListener('click', function () { toggleRead(file.path); br.textContent = state.readSet[file.path] ? '✅' : '⬜'; });
    var bc = $('#btnCopyPath', doc);
    if (bc) bc.addEventListener('click', function () { copyText(file.path); });
    var bo = $('#btnOpenTab', doc);
    if (bo) bo.addEventListener('click', function () { window.open(R.fileUrl(file.path), '_blank'); });

    // 不可渲染文件：路径点击复制
    $$('.nv-path', doc).forEach(function (el) {
      el.addEventListener('click', function () { copyText(el.dataset.copy || ''); });
    });

    buildToc(result.toc || []);
  }

  function kindLabel(f) {
    var m = { markdown: 'Markdown', notebook: 'Jupyter Notebook', code: f.language || '代码',
              text: '纯文本', pdf: 'PDF', image: '图片', html: 'HTML', binary: '二进制', unknown: '未知' };
    return m[f.kind] || f.kind;
  }

  function showError(msg, path) {
    $('#welcome').hidden = true;
    var doc = $('#doc');
    doc.hidden = false;
    doc.innerHTML = '<div class="noview"><div class="nv-ico">⚠️</div><h3>打开失败</h3>' +
      '<p>' + R.esc(msg) + '</p><div class="nv-path">' + R.esc(path || '') + '</div></div>';
    buildToc([]);
  }

  /* =================================================================
     面包屑
     ================================================================= */
  function setCrumbs(path) {
    var parts = path.split('/');
    var html = '<a href="#/">根目录</a>';
    var acc = '';
    parts.forEach(function (p, i) {
      acc = acc ? acc + '/' + p : p;
      html += '<span class="sep">›</span>';
      if (i === parts.length - 1) {
        html += '<span class="cur">' + R.esc(p) + '</span>';
      } else {
        html += '<a href="#/" data-dir="' + R.esc(acc) + '">' + R.esc(p) + '</a>';
      }
    });
    $('#crumbs').innerHTML = html;
  }

  /* =================================================================
     TOC
     ================================================================= */
  function buildToc(toc) {
    var box = $('#toc'), nav = $('#tocNav');
    if (state.tocHidden || !toc || !toc.length) {
      box.hidden = true;
      return;
    }
    box.hidden = false;
    nav.innerHTML = toc.map(function (h) {
      return '<a class="toc-link lv' + h.level + '" href="#' + encodeURI(h.id) +
             '" data-target="' + R.esc(h.id) + '">' + R.esc(h.text) + '</a>';
    }).join('');

    $$('.toc-link', nav).forEach(function (a) {
      a.addEventListener('click', function (ev) {
        ev.preventDefault();
        var el = document.getElementById(a.dataset.target);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });

    if (state.tocObserver) state.tocObserver.disconnect();
    var content = $('#content');
    var links = $$('.toc-link', nav);
    var targets = toc.map(function (h) { return document.getElementById(h.id); }).filter(Boolean);
    state.tocObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        links.forEach(function (l) { l.classList.toggle('active', l.dataset.target === en.target.id); });
      });
    }, { root: content, rootMargin: '-10px 0px -78% 0px', threshold: 0 });
    targets.forEach(function (t) { state.tocObserver.observe(t); });
  }

  /* =================================================================
     最近 / 进度
     ================================================================= */
  function addRecent(file) {
    state.recent = state.recent.filter(function (r) { return r.path !== file.path; });
    state.recent.unshift({ path: file.path, name: file.name, ts: Date.now() });
    state.recent = state.recent.slice(0, 60);
    lsSet(LS.recent, state.recent);
    renderRecent();
  }

  function renderRecent() {
    var box = $('#recentList');
    if (!state.recent.length) {
      box.innerHTML = '<div class="pane-hint">还没有浏览记录</div>';
      return;
    }
    box.innerHTML = state.recent.map(function (r) {
      var dir = r.path.split('/').slice(0, -1).join(' / ');
      return '<div class="ritem" data-path="' + R.esc(r.path) + '">' +
             '<div class="rn">' + R.esc(r.name) + '</div>' +
             '<div class="rp">' + R.esc(dir) + '</div></div>';
    }).join('');
    $$('.ritem', box).forEach(function (el) {
      el.addEventListener('click', function () {
        location.hash = '#/' + encodeURI(el.dataset.path);
      });
    });
  }

  function toggleRead(path, force) {
    var on = force != null ? force : !state.readSet[path];
    if (on) state.readSet[path] = 1; else delete state.readSet[path];
    lsSet(LS.read, state.readSet);
    var row = document.querySelector('.trow[data-path="' + cssEsc(path) + '"]');
    if (row) row.classList.toggle('read', !!on);
    renderProgress();
    // 首页课时按钮上的已读状态也要跟着更新
    if (!$('#welcome').hidden) { renderStats(); renderTimeline(); renderExtra(); }
    return on;
  }

  function startReadTimer(file) {
    clearTimeout(state.readTimer);
    if (state.readSet[file.path]) return;
    state.readTimer = setTimeout(function () {
      if (state.current && state.current.path === file.path) {
        toggleRead(file.path, true);
        var br = $('#btnRead');
        if (br) br.textContent = '✅';
        toast('已自动标记为已读');
      }
    }, 30000);
  }

  function renderProgress() {
    var box = $('#progressList');
    if (!state.stats) { box.innerHTML = '<div class="pane-hint">加载中…</div>'; return; }
    var read = state.readSet;
    var html = state.stats.sections.map(function (s) {
      // 统计该版块已读数
      var cnt = 0;
      Object.keys(read).forEach(function (p) {
        if (p.indexOf(s.name + '/') === 0) cnt++;
      });
      var pct = s.files ? Math.min(100, Math.round(cnt / s.files * 100)) : 0;
      return '<div class="pitem"><div class="pt"><b>' + R.esc(s.name) + '</b>' +
             '<span>' + cnt + ' / ' + s.files + '</span></div>' +
             '<div class="ptrack"><div class="pfill" style="width:' + pct + '%"></div></div>' +
             '<div style="font-size:11px;color:var(--ink4);margin-top:4px">' +
             R.humanSize(s.size) + ' · ' + s.repos + ' 个仓库</div></div>';
    }).join('');
    box.innerHTML = html;
  }

  /* =================================================================
     搜索
     ================================================================= */
  var searchTimer;
  function openSearch() {
    $('#searchOverlay').hidden = false;
    var inp = $('#searchInput');
    inp.value = '';
    inp.focus();
    $('#searchResults').innerHTML = '';
    $('#searchHint').textContent = '支持 Markdown / 代码 / Notebook 内容搜索';
  }
  function closeSearch() { $('#searchOverlay').hidden = true; }

  function doSearch(q) {
    var box = $('#searchResults');
    box.innerHTML = '<div class="search-empty">搜索中…</div>';
    api('/api/search', { q: q, limit: 100 }).then(function (data) {
      if (data.error) { box.innerHTML = '<div class="search-empty">' + R.esc(data.error) + '</div>'; return; }
      if (!data.results.length) {
        box.innerHTML = '<div class="search-empty">没有找到匹配「' + R.esc(q) + '」的内容</div>';
        return;
      }
      $('#searchHint').textContent = '命中 ' + data.count + ' 个文件 / ' +
        data.totalHits + ' 处，耗时 ' + data.elapsed + 's';
      box.innerHTML = data.results.map(function (r) {
        var hits = r.hits.map(function (h) {
          var txt = R.esc(h.text);
          var needle = R.esc(q);
          var re = new RegExp(needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
          txt = txt.replace(re, function (m) { return '<mark>' + m + '</mark>'; });
          return '<div class="sh' + (h.match ? ' match' : '') + '">' +
                 '<span class="ln">' + h.line + '</span>' + txt + '</div>';
        }).join('');
        return '<div class="sres" data-path="' + R.esc(r.path) + '">' +
               '<div class="sn">' + R.esc(r.name) +
               '<span class="badge">' + r.count + ' 处</span></div>' +
               '<div class="sp">' + R.esc(r.path) + '</div>' + hits + '</div>';
      }).join('');
      $$('.sres', box).forEach(function (el) {
        el.addEventListener('click', function () {
          closeSearch();
          location.hash = '#/' + encodeURI(el.dataset.path);
        });
      });
    }).catch(function (e) {
      box.innerHTML = '<div class="search-empty">搜索失败: ' + R.esc(e.message) + '</div>';
    });
  }

  /* =================================================================
     主题 / 侧栏 / 复制
     ================================================================= */
  function setTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    $('#hljs-light').disabled = (t === 'dark');
    $('#hljs-dark').disabled = (t !== 'dark');
    lsSet(LS.theme, t);
  }

  function toggleSidebar() {
    var sb = $('#sidebar');
    sb.classList.toggle('collapsed');
    lsSet(LS.sidebar, sb.classList.contains('collapsed'));
  }

  function copyText(t) {
    if (!t) return;
    var ta = document.createElement('textarea');
    ta.value = t;
    ta.style.cssText = 'position:fixed;opacity:0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); toast('已复制: ' + (t.length > 46 ? t.slice(0, 46) + '…' : t)); }
    catch (e) { toast('复制失败'); }
    document.body.removeChild(ta);
  }

  /* =================================================================
     首页：学习路线
     ================================================================= */
  var RM = window.ROADMAP || { stages: [], sections: {}, agentPath: [] };

  /* 展开左侧目录树到指定目录，并高亮定位 */
  function revealDir(path) {
    var parts = path.split('/');
    var chain = [];
    var acc = '';
    for (var i = 0; i < parts.length; i++) {
      acc = acc ? acc + '/' + parts[i] : parts[i];
      chain.push(acc);
    }
    var idx = 0;
    (function step() {
      if (idx >= chain.length) {
        var row = document.querySelector('.trow[data-path="' + cssEsc(path) + '"]');
        if (row) {
          if ($('#sidebar').classList.contains('collapsed')) toggleSidebar();
          row.scrollIntoView({ block: 'center', behavior: 'smooth' });
          row.classList.add('active');
          setTimeout(function () { row.classList.remove('active'); }, 1600);
        }
        return;
      }
      var p = chain[idx++];
      var kids = document.querySelector('.tchildren[data-path="' + cssEsc(p) + '"]');
      if (!kids) { step(); return; }
      var row = kids.parentElement.querySelector('.trow');
      state.expanded[p] = true;
      if (row) row.querySelector('.tarrow').classList.add('open');
      kids.hidden = false;
      var load = (kids.dataset.loaded === '0')
        ? loadTree(p, kids, p.split('/').length)
        : Promise.resolve();
      load.then(function () { setTimeout(step, 16); });
    })();
  }

  /* 打开一个课时 / 文件（三处共用） */
  function openPath(p) {
    if (!p) return;
    location.hash = '#/' + encodeURI(p);
  }

  /* 课时按钮 —— 支持来源标签（src）与 Python 源码标记（py） */
  function lessonBtn(it, label) {
    var py = it.py
      ? '<span class="lpy" data-py="' + R.esc(it.py) + '" title="打开 Python 源码">py</span>'
      : '';
    return '<button class="lesson' + (state.readSet[it.path] ? ' done' : '') +
             '" data-path="' + R.esc(it.path) + '" title="' +
             R.esc(it.tech ? it.title + ' — ' + it.tech : it.path) + '">' +
             (it.src ? '<span class="lsrc s-' + R.esc(it.src) + '">' + R.esc(it.src) + '</span>' : '') +
             '<span class="lno">' + R.esc(label != null ? label : it.no) + '</span>' +
             '<span class="lt">' + R.esc(it.title) + '</span>' +
             (it.tech ? '<span class="ltech">' + R.esc(it.tech) + '</span>' : '') +
             py +
           '</button>';
  }

  /* 顶部统计 */
  function renderStats() {
    var st = $('#welcomeStats');
    if (!st) return;
    if (!state.stats) {
      st.innerHTML = '<div class="wstat"><b>—</b><span>统计中…</span></div>';
      return;
    }
    var lessons = (RM.stages || []).reduce(function (n, s) { return n + (s.items || []).length; }, 0);
    var readCount = Object.keys(state.readSet).length;
    st.innerHTML =
      '<div class="wstat"><b>' + (RM.courses || []).length + '</b><span>套官方课程</span></div>' +
      '<div class="wstat"><b>' + lessons + '</b><span>主线课时</span></div>' +
      '<div class="wstat"><b>' + state.stats.totalFiles.toLocaleString() + '</b><span>文件</span></div>' +
      '<div class="wstat"><b>' + readCount + '</b><span>已读</span></div>';
  }

  /* 绑定课时按钮：点主体开讲义，点 py 标记开源码 */
  function bindLessons(box) {
    $$('.lesson', box).forEach(function (b) {
      b.addEventListener('click', function (e) {
        if (e.target.classList && e.target.classList.contains('lpy')) return;
        openPath(b.dataset.path);
      });
    });
    $$('.lpy', box).forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.stopPropagation();
        openPath(el.dataset.py);
      });
    });
  }

  /* 课程卡片 */
  function renderCourses() {
    var box = $('#rmCourses');
    if (!box) return;
    var sub = $('#rmCoursesSub');
    if (sub) {
      sub.innerHTML = 'MIT 许可的开源课程，已做本地化以便离线阅读。'
        + '自带侧栏与上下章导航 —— 点「开始学习」进入课程主页后，可直接在页面里翻页。';
    }

    box.innerHTML = (RM.courses || []).map(function (c) {
      var lessonsTxt = c.lessons ? (c.lessons + ' 课时') : '路线图';
      return '<div class="ccard' + (c.star ? ' star' : '') + '" data-entry="' + R.esc(c.entry) + '">' +
        '<div class="chead">' +
          '<span class="corg">' + R.esc(c.org) + '</span>' +
          '<span class="cbadge">' + R.esc(c.badge) + '</span>' +
        '</div>' +
        '<div class="cname">' + R.esc(c.name) + '</div>' +
        '<div class="cmeta">' + lessonsTxt + ' · ' + R.esc(c.level) + '</div>' +
        '<div class="cdesc">' + R.esc(c.desc) + '</div>' +
        (c.note ? '<div class="cnote">' + R.esc(c.note) + '</div>' : '') +
        '<div class="cactions">' +
          '<button class="rm-btn primary" data-go="' + R.esc(c.entry) + '">开始学习</button>' +
          '<button class="rm-btn" data-dir="' + R.esc(c.dir) + '">在目录中定位</button>' +
        '</div>' +
      '</div>';
    }).join('');

    $$('[data-go]', box).forEach(function (b) {
      b.addEventListener('click', function (e) { e.stopPropagation(); openPath(b.dataset.go); });
    });
    $$('[data-dir]', box).forEach(function (b) {
      b.addEventListener('click', function (e) { e.stopPropagation(); revealDir(b.dataset.dir); });
    });
    $$('.ccard', box).forEach(function (el) {
      el.addEventListener('click', function () { openPath(el.dataset.entry); });
    });
  }

  /* 四阶段主线 */
  function renderTimeline() {
    var box = $('#rmTimeline');
    if (!box) return;
    box.innerHTML = (RM.stages || []).map(function (s) {
      var items = (s.items || []).map(function (it) { return lessonBtn(it); }).join('');
      return '<div class="stage' + (s.key ? ' key' : '') + '">' +
        '<div class="stage-card">' +
          '<div class="stage-head">' +
            '<span class="stage-no">' + R.esc(s.no) + '</span>' +
            '<span class="stage-title">' + R.esc(s.title) + '</span>' +
            (s.badge ? '<span class="stage-badge">' + R.esc(s.badge) + '</span>' : '') +
            '<span class="stage-time">' + R.esc(s.time) + '</span>' +
          '</div>' +
          '<div class="stage-desc">' + R.esc(s.desc) + '</div>' +
          (items ? '<div class="lessons">' + items + '</div>' : '') +
          (s.pass ? '<div class="stage-pass"><b>过关标准</b>' + R.esc(s.pass) + '</div>' : '') +
        '</div></div>';
    }).join('');

    bindLessons(box);
  }

  /* 选修课时 */
  function renderExtra() {
    var box = $('#rmExtra');
    if (!box) return;
    if (!RM.extra) { box.innerHTML = ''; return; }
    var items = (RM.extra.items || []).map(function (it) { return lessonBtn(it); }).join('');
    box.innerHTML =
      '<h2 class="rm-h2">' + R.esc(RM.extra.title) + '</h2>' +
      '<div class="rm-sub">' + R.esc(RM.extra.sub) + '</div>' +
      '<div class="lessons wrap">' + items + '</div>';
    bindLessons(box);
  }

  /* Agent 专项（阶段④重点课时精编） */
  /* 按目标选路径 */
  function renderPaths() {
    var box = $('#rmPaths');
    if (!box) return;
    if (!RM.paths) { box.innerHTML = ''; return; }
    var cards = (RM.paths.items || []).map(function (p) {
      return '<div class="pcard">' +
               '<div class="pt2">' + R.esc(p.t) + '</div>' +
               '<div class="pd">' + R.esc(p.d) + '</div>' +
               '<div class="pch">' + R.esc(p.chapters) + '</div>' +
             '</div>';
    }).join('');
    box.innerHTML =
      '<h2 class="rm-h2">' + R.esc(RM.paths.title) + '</h2>' +
      '<div class="rm-sub">' + R.esc(RM.paths.sub) + '</div>' +
      '<div class="path-grid">' + cards + '</div>';
  }

  /* Agent 专项（数据为 null 时整块隐藏） */
  function renderAgent() {
    var box = $('#rmAgent');
    if (!box) return;
    if (!RM.agentPath || !RM.agentPath.length) { box.innerHTML = ''; return; }
    var items = (RM.agentPath || []).map(function (it, i) { return lessonBtn(it, i + 1); }).join('');
    box.innerHTML =
      '<h2 class="rm-h2">重点章节</h2>' +
      '<div class="rm-sub">从 37 章中挑出的关键课时，建议按序推进。</div>' +
      '<div class="agent-box"><div class="lessons wrap">' + items + '</div>' +
      '<div class="agent-tip">学完这些后，<b>自己提一个真实需求，从零做一个 Agent</b>。跑 100 个 demo 不如亲手做一个完整项目。</div></div>';
    bindLessons(box);
  }

  function renderEnv() {
    var box = $('#rmEnv');
    if (!box || !RM.env) return;
    box.innerHTML =
      '<h2 class="rm-h2">' + R.esc(RM.env.title) + '</h2>' +
      '<div class="rm-sub">' + R.esc(RM.env.sub) + '</div>' +
      '<pre class="rm-pre">' + R.esc(RM.env.code) + '</pre>' +
      '<div class="rm-note">' + RM.env.note + '</div>';
  }

  function renderIdm() {
    var box = $('#rmIdm');
    if (!box || !RM.idm) return;
    var groups = (RM.idm.groups || []).map(function (g) {
      return '<div class="idm-card"><span class="in">' + R.esc(g.n) + '</span>' +
             '<div class="it">' + R.esc(g.t) + '</div>' +
             '<div class="id">' + R.esc(g.d) + '</div></div>';
    }).join('');
    var books = (RM.onlineBooks || []).map(function (b) {
      return '<a href="' + R.esc(b.u) + '" target="_blank" rel="noopener noreferrer">' +
             R.esc(b.t) + '</a>';
    }).join('');
    box.innerHTML =
      '<h2 class="rm-h2">' + R.esc(RM.idm.title) + '</h2>' +
      '<div class="rm-sub">' + R.esc(RM.idm.sub) + '</div>' +
      '<div class="rm-note">' + RM.idm.note + '</div>' +
      '<div class="idm-grid">' + groups + '</div>' +
      '<div class="rm-actions">' +
        '<button class="rm-btn primary" data-open="' + R.esc(RM.idm.file) + '">打开导入清单</button>' +
        '<button class="rm-btn" data-open="' + R.esc(RM.idm.doc) + '">查看使用说明</button>' +
      '</div>' +
      (books ? '<div class="rm-sub" style="margin:18px 0 0;padding-left:0">在线书籍（HTML 站点，浏览器直接看）</div>' +
               '<div class="online-books">' + books + '</div>' : '');

    $$('[data-open]', box).forEach(function (btn) {
      btn.addEventListener('click', function () {
        location.hash = '#/' + encodeURI(btn.dataset.open);
      });
    });
  }

  function renderWelcome() {
    renderStats();
    renderCourses();
    renderPaths();
    renderTimeline();
    renderExtra();
    renderAgent();
    renderEnv();
    renderIdm();
  }

  /* =================================================================
     路由
     ================================================================= */
  function route() {
    var path = parseHash();
    if (!path) {
      state.current = null;
      $('#welcome').hidden = false;
      $('#doc').hidden = true;
      $('#crumbs').innerHTML = '';
      $('#toc').hidden = true;
      document.title = 'agent学习平台';
      // 回到首页时刷新进度（可能刚读过文件）
      if (state.stats) { renderStats(); renderTimeline(); renderExtra(); }
      expandTo('', null);
      syncFab();
      if (window.Companion) window.Companion.updateContext(null);
      return;
    }
    openFile(path);
    expandTo(path, null);
    syncFab();
  }

  function markActiveInTree(path) {
    $$('.trow.active').forEach(function (r) { r.classList.remove('active'); });
    var row = document.querySelector('.trow[data-path="' + cssEsc(path) + '"]');
    if (row) row.classList.add('active');
  }

  /* =================================================================
     面板切换 / 快捷键
     ================================================================= */
  /* =================================================================
     右下角浮动导航（回根目录 / 回顶部）
     ================================================================= */
  function scrollTop() {
    var c = $('#content');
    if (c) c.scrollTo({ top: 0, behavior: 'smooth' });
    else window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function goHome() { location.hash = '#/'; }

  function initFab() {
    var stack = $('#fabStack'), fabTop = $('#fabTop'), fabHome = $('#fabHome');
    if (!stack || !fabTop || !fabHome) return;

    fabHome.addEventListener('click', goHome);
    fabTop.addEventListener('click', scrollTop);

    // 滚动超过一屏才出现「回顶部」
    var content = $('#content');
    var ticking = false;
    state.fabScroll = function () {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () {
        var st = content ? content.scrollTop : (window.scrollY || 0);
        fabTop.hidden = st < 400;
        ticking = false;
      });
    };
    if (content) content.addEventListener('scroll', state.fabScroll, { passive: true });
    window.addEventListener('scroll', state.fabScroll, { passive: true });
    state.fabScroll();
  }

  /* 路由变化时同步浮动按钮：首页不显示「回根目录」 */
  function syncFab() {
    var fabHome = $('#fabHome');
    if (!fabHome) return;
    var h = location.hash;
    fabHome.hidden = (!h || h === '#' || h === '#/');
    if (state.fabScroll) state.fabScroll();
  }

  /* 同步「显示全部文件」按钮的视觉状态 */
  function syncAllFilesBtn() {
    var b = $('#btnAllFiles');
    if (!b) return;
    var on = !!state.showAllFiles;
    b.classList.toggle('on', on);
    b.textContent = on ? '◉' : '◎';
    b.title = on ? '当前显示全部文件（点此隐藏 README 等）'
                 : '当前只显示学习内容（点此显示 README 等工程文件）';
  }

  function bindPanels() {
    $$('.side-tab').forEach(function (tab) {
      tab.addEventListener('click', function () {
        $$('.side-tab').forEach(function (t) { t.classList.remove('active'); });
        tab.classList.add('active');
        ['tree', 'recent', 'progress'].forEach(function (p) {
          $('#pane-' + p).hidden = (p !== tab.dataset.pane);
        });
        if (tab.dataset.pane === 'progress') renderProgress();
        if (tab.dataset.pane === 'recent') renderRecent();
      });
    });
  }

  function bindKeys() {
    document.addEventListener('keydown', function (ev) {
      var mod = ev.ctrlKey || ev.metaKey;
      if (mod && ev.key.toLowerCase() === 'k') { ev.preventDefault(); openSearch(); return; }
      if (mod && ev.key.toLowerCase() === 'b') { ev.preventDefault(); toggleSidebar(); return; }
      if (mod && ev.key.toLowerCase() === 'i') {
        ev.preventDefault();
        state.tocHidden = !state.tocHidden;
        lsSet(LS.toc, state.tocHidden);
        if (state.current) openFile(state.current.path, { noHash: true });
        return;
      }
      if (ev.key === 'Escape') { closeSearch(); return; }
      // AI 陪读
      if (mod && ev.key.toLowerCase() === 'j') {
        ev.preventDefault();
        if (window.Companion) window.Companion.toggle();
        return;
      }
      // 浮动导航快捷键
      if (ev.altKey && ev.key === 'Home') { ev.preventDefault(); goHome(); return; }
      if (ev.altKey && ev.key === 'ArrowUp') { ev.preventDefault(); scrollTop(); return; }
      if (ev.key === '/' && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) {
        ev.preventDefault(); openSearch();
      }
    });
  }

  /* =================================================================
     启动
     ================================================================= */
  function boot() {
    // 恢复偏好
    var theme = lsGet(LS.theme, null);
    if (!theme) {
      theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    setTheme(theme);
    state.readSet = lsGet(LS.read, {});
    state.recent = lsGet(LS.recent, []);
    state.tocHidden = lsGet(LS.toc, false);
    state.showAllFiles = lsGet('studyai.allfiles', false);
    if (lsGet(LS.sidebar, false)) $('#sidebar').classList.add('collapsed');
    syncAllFilesBtn();

    // 事件
    $('#btnTheme').addEventListener('click', function () {
      setTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
    });
    $('#btnSidebar').addEventListener('click', toggleSidebar);
    $('#btnSearch').addEventListener('click', openSearch);
    $('#btnSearchClose').addEventListener('click', closeSearch);
    // AI 陪读
    var btnCp = $('#btnCompanion');
    if (btnCp) btnCp.addEventListener('click', function () {
      if (window.Companion) window.Companion.toggle();
    });
    if (window.Companion) window.Companion.init();
    $('#btnToc').addEventListener('click', function () {
      state.tocHidden = !state.tocHidden;
      lsSet(LS.toc, state.tocHidden);
      if (state.current) buildToc(state.current._toc || []);
    });
    $('#searchOverlay').addEventListener('click', function (ev) {
      if (ev.target.id === 'searchOverlay') closeSearch();
    });
    $('#searchInput').addEventListener('input', function (ev) {
      var q = ev.target.value.trim();
      clearTimeout(searchTimer);
      if (q.length < 2) {
        $('#searchResults').innerHTML = '';
        $('#searchHint').textContent = '支持 Markdown / 代码 / Notebook 内容搜索';
        return;
      }
      searchTimer = setTimeout(function () { doSearch(q); }, 320);
    });
    $('#treeFilter').addEventListener('input', function (ev) {
      state.filter = ev.target.value;
      applyFilter();
    });
    $('#btnCollapseAll').addEventListener('click', function () {
      $$('.tchildren').forEach(function (c) { c.hidden = true; });
      $$('.tarrow').forEach(function (a) { a.classList.remove('open'); });
      state.expanded = {};
      toast('已全部收起');
    });
    // 显示/隐藏 README、LICENSE 这类工程文件
    $('#btnAllFiles').addEventListener('click', function () {
      state.showAllFiles = !state.showAllFiles;
      lsSet('studyai.allfiles', state.showAllFiles);
      syncAllFilesBtn();
      state.treeCache = {};          // 缓存里含被过滤的条目，必须清掉重建
      state.expanded = {};
      initTree().then(function () { toast(state.showAllFiles ? '已显示全部文件' : '已隐藏工程文件'); });
    });
    $('#crumbs').addEventListener('click', function (ev) {
      var a = ev.target.closest('a[data-dir]');
      if (!a) return;
      ev.preventDefault();
      var p = a.dataset.dir;
      var c = document.querySelector('.tchildren[data-path="' + cssEsc(p) + '"]');
      if (c) {
        var row = c.parentElement.querySelector('.trow');
        if (row && c.hidden) toggleDir(row, c, p, p.split('/').length);
        if (row) row.scrollIntoView({ block: 'center' });
      }
    });

    bindTree();
    bindPanels();
    bindKeys();
    initFab();
    window.addEventListener('hashchange', route);

    // 路线页：静态部分只渲染一次（不依赖统计数据）
    renderCourses();
    renderPaths();
    renderTimeline();
    renderExtra();
    renderAgent();
    renderEnv();
    renderIdm();

    // 数据：统计较慢（需遍历全部文件），改为不阻塞首屏
    loading(true);
    api('/api/stats').then(function (s) {
      state.stats = s;
      renderStats();
      renderProgress();
    }).catch(function () {});

    initTree().then(function () {
      renderStats();          // 先出骨架
      renderRecent();
      renderProgress();
      route();
      loading(false);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
