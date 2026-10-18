/* =====================================================================
   手机版外壳（static/m/）
   与电脑版共用：renderers.js（渲染）、companion.js（陪读）、后端 API
   本文件只负责手机版的布局逻辑：路由、目录抽屉、文档渲染、悬浮球
   ===================================================================== */
(function () {
  'use strict';

  var R = window.Renderers;
  var $  = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  var LS = { read: 'studyai.read', last: 'studyai.m.last' };

  var state = {
    cur: null,        // 当前文件
    tree: null,       // 根目录树
    readSet: {},
    drawerOpen: false
  };

  /* ---------------- 基础工具 ---------------- */
  function lsGet(k, d) {
    try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; }
  }
  function lsSet(k, v) {
    try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {}
  }
  function api(path, params) {
    var q = Object.keys(params || {}).map(function (k) {
      return encodeURIComponent(k) + '=' + encodeURIComponent(params[k]);
    }).join('&');
    return fetch(path + (q ? '?' + q : '')).then(function (r) {
      if (!r.ok) return r.json().then(function (e) { throw new Error(e.error || ('HTTP ' + r.status)); });
      return r.json();
    });
  }
  function toast(msg) {
    var el = $('#mToast');
    if (!el) return;
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(el._t);
    el._t = setTimeout(function () { el.hidden = true; }, 1800);
  }

  /* ---------------- 路由 ---------------- */
  function parseHash() {
    var h = location.hash || '';
    if (h.indexOf('#/') !== 0) return null;
    var raw = h.slice(2);
    if (!raw) return null;
    try { return decodeURI(raw); } catch (e) { return raw; }
  }

  function goHome() {
    location.hash = '#/';
  }

  function route() {
    var path = parseHash();
    if (!path) { showHome(); return; }
    openFile(path);
  }

  /* ---------------- 首页 ---------------- */
  function showHome() {
    state.cur = null;
    $('#mTitle').textContent = 'agent学习平台';
    $('#mBack').hidden = true;
    $('#doc').hidden = true;
    var home = $('#mHome');
    home.hidden = false;
    var _sb = document.getElementById('mStartBar');
    if (_sb) _sb.hidden = true;

    var last = lsGet(LS.last, null);
    var resume = $('#mResume');
    if (last && last.path) {
      resume.hidden = false;
      resume.innerHTML =
        '<button class="m-resume-btn" id="mResumeBtn">' +
          '<span class="m-resume-ico">↩</span>' +
          '<span class="m-resume-txt"><b>继续上次</b><i>' + R.esc(last.title || last.path) + '</i></span>' +
        '</button>';
      $('#mResumeBtn').addEventListener('click', function () {
        location.hash = '#/' + encodeURI(last.path);
      });
    } else {
      resume.hidden = true;
    }

    // 资源卡
    if (window.LIBRARY && !$('#mCards').childElementCount) {
      $('#mCards').innerHTML = window.LIBRARY.map(function (r) {
        return '<button class="m-card m-' + R.esc(r.accent) + '" data-entry="' + R.esc(r.entry) + '">' +
                 '<span class="m-card-ico">' + R.esc(r.icon) + '</span>' +
                 '<span class="m-card-body">' +
                   '<b>' + R.esc(r.name) + '</b>' +
                   '<i>' + R.esc(r.level) + ' · ' + R.esc(r.volume) + '</i>' +
                 '</span>' +
                 '<span class="m-card-arrow">›</span>' +
               '</button>';
      }).join('');
    }
    if (window.Companion) window.Companion.updateContext(null);
  }

  /* ---------------- 打开文件 ---------------- */
  function openFile(path) {
    $('#mHome').hidden = true;
    $('#doc').hidden = false;
    $('#mBack').hidden = false;
    $('#doc').innerHTML = '<div class="m-loading">加载中…</div>';

    api('/api/file', { path: path }).then(function (file) {
      state.cur = file;
      renderDoc(file);

      var title = file.name.replace(/\.[^.]+$/, '');
      $('#mTitle').textContent = title;
      document.title = title + ' · agent学习平台';

      // 记住"上次读到哪"
      if (!/\/index\.html?$/i.test(file.path)) {
        lsSet(LS.last, { path: file.path, title: title });
      }

      // 标记已读
      state.readSet[file.path] = 1;
      lsSet(LS.read, state.readSet);

      // 回到顶部
      $('#doc').scrollTop = 0;
      window.scrollTo(0, 0);

      showStartBar(file);
      if (window.Companion) window.Companion.updateContext(file);
    }).catch(function (e) {
      $('#doc').innerHTML = '<div class="m-error">打开失败：' + R.esc(e.message) + '</div>';
    });
  }

  function renderDoc(file) {
    var box = $('#doc');
    var r;
    try { r = R.render(file); }
    catch (e) { box.innerHTML = '<div class="m-error">渲染失败：' + R.esc(e.message) + '</div>'; return; }

    box.innerHTML = r.html;
    box.className = 'm-doc m-doc--' + (r.type || 'text');

    // 目录（companion.js 需要这个元素）
    var toc = $('#toc');
    toc.hidden = true;
    toc.innerHTML = '';

    if (r.type === 'html' || r.type === 'pdf') {
      // 整页 HTML / PDF：占满，不留正文内边距
      box.classList.add('m-doc--full');
    }

    // 底部「上一章 / 下一章」
    if (r.type !== 'html' && r.type !== 'pdf') {
      appendNav(box, file);
    }

    // 站内链接改写：拦截点击走 hash 路由
    box.addEventListener('click', onDocClick, true);
  }

  function onDocClick(ev) {
    var a = ev.target.closest && ev.target.closest('a[data-internal="1"]');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    if (href.indexOf('#/') === 0) {
      ev.preventDefault();
      location.hash = href;
    }
  }

  /* ---------------- 资源首页底部的「开始学习」 ----------------
     打开课程的 index.html 时，章节入口在页面底部不好找，
     这里给一条常驻底栏，一键跳到本资源的第一章。 */
  function showStartBar(file) {
    var bar = $('#mStartBar');
    if (!bar) {
      bar = document.createElement('button');
      bar.id = 'mStartBar';
      bar.className = 'm-startbar';
      bar.hidden = true;
      document.body.appendChild(bar);
      bar.addEventListener('click', function () {
        var p = bar.dataset.go;
        if (p) location.hash = '#/' + encodeURI(p);
      });
    }

    // 只有"资源首页"才显示：路径形如 0X-xxx/index.html
    var isIndex = /^[^\/]+\/index\.html?$/i.test(file.path);
    if (!isIndex) { bar.hidden = true; return; }

    var resDir = file.path.split('/')[0];
    bar.hidden = false;
    bar.disabled = true;
    bar.innerHTML = '<span>正在找第一章…</span>';

    // 找到该资源下第一个 chapter_* 目录里的第一个 html
    api('/api/tree', { path: resDir }).then(function (t) {
      var chs = (t.dirs || []).filter(function (d) { return /^chapter_\d+/.test(d.name); })
        .sort(function (a, b) { return a.name < b.name ? -1 : 1; });
      // AFA 没有 chapter_ 目录，走 book/
      var book = (t.dirs || []).filter(function (d) { return d.name === 'book'; })[0];
      var first = null;

      function done(p) {
        if (!p) { bar.hidden = true; return; }
        bar.dataset.go = p;
        bar.disabled = false;
        bar.innerHTML = '<span>开始学习 →</span>';
      }

      if (chs.length) {
        api('/api/tree', { path: chs[0].path }).then(function (c) {
          var f = (c.files || []).filter(function (x) { return /\.html?$/i.test(x.name) && x.renderable; })[0];
          done(f ? f.path : null);
        }).catch(function () { done(null); });
      } else if (book) {
        api('/api/tree', { path: book.path }).then(function (b) {
          var fs = (b.files || []).filter(function (x) { return /\.md$/i.test(x.name); })
            .sort(function (a, c) { return a.name < c.name ? -1 : 1; });
          done(fs.length ? fs[0].path : null);
        }).catch(function () { done(null); });
      } else {
        done(null);
      }
    }).catch(function () { bar.hidden = true; });
  }

  /* ---------------- 上一章 / 下一章 ---------------- */

  // 全局阅读顺序：AFA 的 book/*.md，以及 AI Agent 每个 chapter 的讲义
  var _orderPromise = null;
  function loadOrder() {
    if (_orderPromise) return _orderPromise;
    _orderPromise = api('/api/tree', { path: '' }).then(function (root) {
      var dirs = (root.dirs || []).filter(function (d) {
        return d.name.indexOf('01-') === 0 || d.name.indexOf('02-') === 0;
      });
      return Promise.all(dirs.map(function (d) {
        return api('/api/tree', { path: d.path }).then(function (t) {
          return { dir: d, tree: t };
        }).catch(function () { return { dir: d, tree: {} }; });
      }));
    }).then(function (groups) {
      var seq = [];
      groups.forEach(function (g) {
        var book = (g.tree.dirs || []).filter(function (x) { return x.name === 'book'; })[0];
        if (book) {
          // AFA：book 下的 md 按名字排序（00, 01, ... 90~94）
          seq.push({ dir: book.path, kind: 'md' });
        }
        (g.tree.dirs || []).filter(function (x) { return /^chapter_\d+/.test(x.name); })
          .forEach(function (c) { seq.push({ dir: c.path, kind: 'chapter' }); });
      });
      // 逐个展开成具体文件
      return Promise.all(seq.map(function (s) {
        return api('/api/tree', { path: s.dir }).then(function (t) {
          var files = (t.files || []).filter(function (f) { return f.renderable; });
          if (s.kind === 'chapter') {
            files = files.filter(function (f) { return /\.html?$/i.test(f.name); });
          } else {
            files = files.filter(function (f) { return /\.md$/i.test(f.name); });
            files.sort(function (a, b) { return a.name < b.name ? -1 : a.name > b.name ? 1 : 0; });
          }
          return files.map(function (f) { return f.path; });
        }).catch(function () { return []; });
      }));
    }).then(function (lists) {
      var out = [];
      lists.forEach(function (l) { out = out.concat(l); });
      return out;
    }).catch(function () { return []; });
    return _orderPromise;
  }

  function appendNav(box, file) {
    loadOrder().then(function (order) {
      if (!order || order.length < 2) return;
      var i = order.indexOf(file.path);
      if (i < 0) return;
      var prev = i > 0 ? order[i - 1] : null;
      var next = i < order.length - 1 ? order[i + 1] : null;
      if (!prev && !next) return;

      var nav = document.createElement('nav');
      nav.className = 'm-nav';
      nav.innerHTML =
        (prev
          ? '<a class="m-nav-a m-nav-prev" href="#/' + encodeURI(prev) + '" data-internal="1">' +
              '<span class="m-nav-dir">← 上一章</span>' +
              '<span class="m-nav-t">' + R.esc(shortName(prev)) + '</span></a>'
          : '<span class="m-nav-a m-nav-empty"></span>') +
        (next
          ? '<a class="m-nav-a m-nav-next" href="#/' + encodeURI(next) + '" data-internal="1">' +
              '<span class="m-nav-dir">下一章 →</span>' +
              '<span class="m-nav-t">' + R.esc(shortName(next)) + '</span></a>'
          : '<span class="m-nav-a m-nav-empty"></span>');

      box.appendChild(nav);
      // 点击走路由
      Array.prototype.forEach.call(nav.querySelectorAll('a'), function (a) {
        a.addEventListener('click', function (ev) {
          ev.preventDefault();
          location.hash = a.getAttribute('href');
          $('#mScroll').scrollTop = 0;
        });
      });
    });
  }

  function shortName(path) {
    var n = String(path).split('/').pop().replace(/\.[^.]+$/, '');
    var m = /^(\d+)-(.+)$/.exec(n);
    if (m) {
      var no = parseInt(m[1], 10);
      if (no >= 90) return '附录' + String.fromCharCode(64 + (no - 90)) + ' · ' + m[2].replace(/^附录[A-D]-?/, '');
      return '第 ' + no + ' 章 · ' + m[2];
    }
    return n.replace(/^chapter_\d+_/, '').replace(/_/g, ' ');
  }

  /* ---------------- 目录抽屉 ---------------- */
  function buildDrawer() {
    var box = $('#mList');
    box.innerHTML = '<div class="m-loading">加载中…</div>';

    api('/api/tree', { path: '' }).then(function (root) {
      state.tree = root;
      var dirs = (root.dirs || []).filter(function (d) {
        return d.name.indexOf('01-') === 0 || d.name.indexOf('02-') === 0;
      });
      if (!dirs.length) { box.innerHTML = '<div class="m-loading">没有找到资源</div>'; return; }

      // 两个资源并行取各自内容
      return Promise.all(dirs.map(function (d) {
        return api('/api/tree', { path: d.path }).then(function (t) {
          return { dir: d, tree: t };
        }).catch(function () { return { dir: d, tree: { dirs: [], files: [] } }; });
      }));
    }).then(function (groups) {
      if (!groups) return;
      box.innerHTML = groups.map(function (g) {
        var chapters = (g.tree.dirs || []).filter(function (d) {
          return /^chapter_\d+/.test(d.name);
        });
        // AFA 是 md 文件（book 目录下的）
        var books = (g.tree.dirs || []).filter(function (d) { return d.name === 'book'; });
        var inner = '';

        if (chapters.length) {
          inner = chapters.map(function (c, i) {
            return '<button class="m-li" data-dir="' + R.esc(c.path) + '">' +
                     '<span class="m-li-no">第' + cnNum(i + 1) + '节</span>' +
                     '<span class="m-li-t">' + R.esc(friendlyTitle(c.name)) + '</span>' +
                   '</button>';
          }).join('');
        }
        if (books.length) {
          inner += '<div class="m-li-hint">点开加载目录…</div>';
        }
        return '<div class="m-group" data-group="' + R.esc(g.dir.path) + '">' +
                 '<div class="m-group-head">' +
                   '<span class="m-group-name">' + R.esc(g.dir.name.replace(/^\d+-/, '')) + '</span>' +
                 '</div>' +
                 '<div class="m-group-body">' + inner + '</div>' +
               '</div>';
      }).join('');

      // 绑定
      $$('.m-li[data-dir]', box).forEach(function (b) {
        b.addEventListener('click', function () { expandChapter(b.dataset.dir, b); });
      });
      $$('[data-group]', box).forEach(function (grp) {
        var g = groups.filter(function (x) { return x.dir.path === grp.dataset.group; })[0];
        var bookDir = g && (g.tree.dirs || []).filter(function (d) { return d.name === 'book'; })[0];
        if (bookDir) {
          var body = $('.m-group-body', grp);
          body.innerHTML = '<div class="m-loading">加载目录…</div>';
          api('/api/tree', { path: bookDir.path }).then(function (bt) {
            var files = (bt.files || []).filter(function (f) { return /\.md$/.test(f.name); });
            body.innerHTML = files.map(function (f) {
              return '<button class="m-li" data-file="' + R.esc(f.path) + '">' +
                       '<span class="m-li-t">' + R.esc(bookTitle(f.name)) + '</span>' +
                     '</button>';
            }).join('') || '<div class="m-loading">（空）</div>';
            $$('.m-li[data-file]', body).forEach(function (b) {
              b.addEventListener('click', function () {
                closeDrawer();
                location.hash = '#/' + encodeURI(b.dataset.file);
              });
            });
          });
        }
      });
    }).catch(function (e) {
      box.innerHTML = '<div class="m-error">目录加载失败：' + R.esc(e.message) + '</div>';
    });
  }

  function cnNum(n) {
    var D = ['零','一','二','三','四','五','六','七','八','九'];
    if (n < 10) return D[n];
    if (n === 10) return '十';
    if (n < 20) return '十' + D[n - 10];
    var t = Math.floor(n / 10), r = n % 10;
    return D[t] + '十' + (r ? D[r] : '');
  }

  // chapter_19_workflow_patterns -> 用 roadmap 里的中文标题
  function friendlyTitle(dirName) {
    var RM = window.ROADMAP || {};
    var hit = null;
    (RM.stages || []).forEach(function (st) {
      (st.items || []).forEach(function (it) {
        if (String(it.path || '').indexOf(dirName) >= 0) hit = it;
      });
    });
    return hit ? hit.title : dirName.replace(/^chapter_\d+_/, '').replace(/_/g, ' ');
  }

  // 00-导论.md -> 第 0 章 导论
  function bookTitle(fileName) {
    var m = /^(\d+)-(.+)\.md$/.exec(fileName);
    if (!m) return fileName.replace(/\.md$/, '');
    var no = parseInt(m[1], 10);
    var name = m[2];
    if (no >= 90) return '附录' + String.fromCharCode(64 + (no - 90)) + ' · ' + name.replace(/^附录[A-D]-?/, '');
    return '第 ' + no + ' 章 · ' + name;
  }

  // 章节文件夹展开成两个文件
  function expandChapter(dirPath, btn) {
    var box = btn.parentElement;
    if (btn.dataset.open === '1') {
      btn.dataset.open = '0';
      var old = $('.m-subs[data-for="' + dirPath + '"]', box);
      if (old) old.remove();
      return;
    }
    btn.dataset.open = '1';
    api('/api/tree', { path: dirPath }).then(function (t) {
      var files = (t.files || []).filter(function (f) { return f.renderable; });
      var subs = document.createElement('div');
      subs.className = 'm-subs';
      subs.dataset.for = dirPath;
      subs.innerHTML = files.map(function (f) {
        var isHtml = /\.html?$/.test(f.name);
        return '<button class="m-sub" data-file="' + R.esc(f.path) + '">' +
                 '<span class="m-sub-dot ' + (isHtml ? 'html' : 'py') + '"></span>' +
                 '<span>' + (isHtml ? '讲义' : 'Python 源码') + '</span>' +
               '</button>';
      }).join('');
      btn.insertAdjacentElement('afterend', subs);
      $$('.m-sub', subs).forEach(function (b) {
        b.addEventListener('click', function () {
          closeDrawer();
          location.hash = '#/' + encodeURI(b.dataset.file);
        });
      });
    });
  }

  function openDrawer() {
    state.drawerOpen = true;
    $('#mDrawer').hidden = false;
    $('#mMask').hidden = false;
    requestAnimationFrame(function () {
      $('#mDrawer').classList.add('on');
      $('#mMask').classList.add('on');
    });
    if (!$('#mList').childElementCount) buildDrawer();
  }
  function closeDrawer() {
    state.drawerOpen = false;
    $('#mDrawer').classList.remove('on');
    $('#mMask').classList.remove('on');
    setTimeout(function () {
      if (!state.drawerOpen) {
        $('#mDrawer').hidden = true;
        $('#mMask').hidden = true;
      }
    }, 240);
  }

  /* ---------------- 悬浮球 ---------------- */
  function syncOrb() {
    var o = $('#cpOrb');
    if (!o || !window.Companion) return;
    var open = window.Companion.isOpen();
    o.classList.toggle('on', open);
    o.setAttribute('aria-label', open ? '收起 AI 陪读' : '打开 AI 陪读');
  }

  function bindOrb() {
    var o = $('#cpOrb');
    if (!o) return;
    o.addEventListener('click', function () {
      if (window.Companion) {
        window.Companion.toggle();
        setTimeout(syncOrb, 30);
      }
    });
    // 面板开关时同步球的状态（companion.js 会改 body.cp-open）
    var mo = new MutationObserver(syncOrb);
    mo.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    syncOrb();
  }

  /* ---------------- 启动 ---------------- */
  function boot() {
    state.readSet = lsGet(LS.read, {});

    // 顶栏
    $('#mBack').addEventListener('click', function () {
      if (history.length > 1) history.back();
      else goHome();
    });
    $('#mMenu').addEventListener('click', openDrawer);
    $('#mMask').addEventListener('click', closeDrawer);

    // 资源卡点击
    $('#mCards').addEventListener('click', function (ev) {
      var c = ev.target.closest('[data-entry]');
      if (!c) return;
      location.hash = '#/' + encodeURI(c.dataset.entry);
    });

    window.addEventListener('hashchange', route);

    // 陪读（共用 companion.js）
    if (window.Companion) window.Companion.init();
    bindOrb();

    route();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
