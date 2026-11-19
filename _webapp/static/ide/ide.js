/* 编辑器页：Monaco + 保存到工作区 + 运行 Python。
   所有写操作都走 /api/ide/*，由后端限制「只能写工作区」。 */
(function () {
  'use strict';

  var qs = new URLSearchParams(location.search);
  // 被阅读器以分栏方式内嵌时（?embed=1），隐藏「← 返回」以免在 iframe 里再套一层阅读器
  if (qs.get('embed')) document.body.classList.add('embed');
  var state = {
    path: qs.get('path') || '',
    name: '',
    enabled: false,
    workspace: '',
    workspaceAbs: '',
    defaultDir: '',
    python: '',
    timeout: 10,
    dirty: false,
    editor: null,
    savedValue: ''
  };

  var el = {
    host: document.getElementById('ideHost'),
    name: document.getElementById('ideName'),
    badge: document.getElementById('ideBadge'),
    mask: document.getElementById('ideMask'),
    btnSave: document.getElementById('btnSave'),
    btnSaveAs: document.getElementById('btnSaveAs'),
    btnRun: document.getElementById('btnRun'),
    btnOut: document.getElementById('btnOut'),
    btnSettings: document.getElementById('btnSettings'),
    out: document.getElementById('ideOutput'),
    outTitle: document.getElementById('ideOutTitle'),
    outBody: document.getElementById('ideOutBody'),
    btnNew: document.getElementById('btnNew')
  };

  var LANG = {
    python: 'python', markdown: 'markdown', javascript: 'javascript',
    typescript: 'typescript', yaml: 'yaml', bash: 'shell', shell: 'shell',
    powershell: 'powershell', json: 'json', html: 'html', css: 'css',
    scss: 'scss', less: 'less', sql: 'sql', ini: 'ini', plaintext: 'plaintext',
    dos: 'bat', c: 'c', cpp: 'cpp', csharp: 'csharp', go: 'go', rust: 'rust',
    java: 'java', ruby: 'ruby', php: 'php', xml: 'xml', r: 'r',
    dockerfile: 'dockerfile', cmake: 'cmake'
  };

  /* ---------- 小工具 ---------- */
  function api(url, body) {
    var opt = { cache: 'no-store' };
    if (body !== undefined) {
      opt.method = 'POST';
      opt.headers = { 'Content-Type': 'application/json' };
      opt.body = JSON.stringify(body);
    }
    return fetch(url, opt).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) {
        if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
        return d;
      });
    });
  }

  function setBadge(text, cls) {
    el.badge.textContent = text;
    el.badge.className = 'ide-badge' + (cls ? ' ' + cls : '');
  }

  function fail(msg) {
    el.mask.hidden = false;
    el.mask.textContent = msg;
    setBadge('无法打开', 'bad');
  }

  function inWorkspace(p) {
    var ws = state.workspace ? state.workspace + '/' : '';
    return !!ws && p.indexOf(ws) === 0;
  }

  function refreshSaveBtn() {
    if (!state.enabled) { el.btnSave.disabled = true; return; }
    el.btnSave.disabled = false;
    el.btnSave.textContent = '保存';
    el.btnSave.title = inWorkspace(state.path)
      ? '保存到 ' + state.path + '（Ctrl+S）'
      : '课程文件只读，点保存会弹出「保存到哪」（Ctrl+S）';
  }

  function refreshTitle() {
    el.name.textContent = (state.name || state.path || '未命名') + (state.dirty ? ' ●' : '');
    el.name.title = state.path;
    document.title = (state.name || '编辑') + (state.dirty ? ' ●' : '') + ' · agent学习平台';
  }

  function preferredTheme() {
    try {
      var saved = localStorage.getItem('studyai.theme');
      if (saved === 'dark' || saved === 'light') return saved;
    } catch (e) { /* 隐私模式 */ }
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(mode) {
    document.body.classList.toggle('dark', mode === 'dark');
    if (state.editor) monaco.editor.setTheme(mode === 'dark' ? 'vs-dark' : 'vs');
  }

  /* ---------- 输出面板 ---------- */
  function showOutput(title, text, kind) {
    el.out.hidden = false;
    el.outTitle.textContent = title;
    el.outTitle.className = 'ide-out-title' + (kind ? ' ' + kind : '');
    el.outBody.textContent = text || '（无输出）';
    el.outBody.scrollTop = 0;
  }

  document.getElementById('btnOut').addEventListener('click', function () {
    el.out.hidden = !el.out.hidden;
  });
  document.getElementById('btnCloseOut').addEventListener('click', function () {
    el.out.hidden = true;
  });
  document.getElementById('btnClearOut').addEventListener('click', function () {
    el.outBody.textContent = '';
    el.outTitle.textContent = '输出';
  });

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function fmtSize(n) {
    if (!n && n !== 0) return '';
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
    return (n / 1048576).toFixed(1) + ' MB';
  }

  /* ---------- 练习区落地页（没带 ?path= 时） ---------- */
  function renderWorkspace() {
    el.name.textContent = state.workspace || '练习区';
    el.btnNew.hidden = false;
    el.btnSave.hidden = true;
    el.btnSaveAs.hidden = true;
    el.btnRun.hidden = true;
    el.btnOut.hidden = true;
    setBadge('练习区', 'ok');

    api('/api/ide/list').then(function (d) {
      el.mask.hidden = true;
      var items = d.items || [];
      if (!items.length) {
        el.host.innerHTML = '<div class="ide-empty">' +
          '<b>练习区还是空的</b><br>' +
          '点右上角「新建」写第一个文件，<br>' +
          '或者在阅读器里打开 .py 文件，点标题栏的 ✎ 另存过来。' +
          '</div>';
        return;
      }
      var html = '<div class="ide-list"><div class="ide-list-head">' +
        items.length + ' 个文件 · ' + esc(d.workspace) + '</div>';
      items.forEach(function (it) {
        html += '<a class="ide-list-row" href="/ide?path=' + encodeURIComponent(it.path) + '">' +
          '<span class="ide-list-name">' + esc(it.name) + '</span>' +
          '<span class="ide-list-meta">' + fmtSize(it.size) + '</span></a>';
      });
      html += '</div>';
      el.host.innerHTML = html;
    }).catch(function (e) { fail('读取练习区失败：' + e.message); });
  }

  /* ---------- 新建文件 ---------- */
  var dlgNew = document.getElementById('dlgNew');
  var newPath = document.getElementById('newPath');
  var newMsg = document.getElementById('newMsg');

  el.btnNew.addEventListener('click', function () {
    newPath.value = '';
    newMsg.textContent = '';
    dlgNew.showModal();
  });

  dlgNew.addEventListener('close', function () {
    if (dlgNew.returnValue !== 'create') return;
    var rel = newPath.value.trim().replace(/\\/g, '/').replace(/^\/+/, '');
    if (!rel) return;
    api('/api/ide/save', { path: state.workspace + '/' + rel, content: '' })
      .then(function (res) { location.href = '/ide?path=' + encodeURIComponent(res.path); })
      .catch(function (e) { newMsg.textContent = e.message; dlgNew.showModal(); });
  });

  /* ---------- 保存 ---------- */
  var dlgSaveAs = document.getElementById('dlgSaveAs');
  var saveAsDir = document.getElementById('saveAsDir');
  var saveAsName = document.getElementById('saveAsName');
  var saveAsRemember = document.getElementById('saveAsRemember');
  var saveAsMsg = document.getElementById('saveAsMsg');
  var saveAsHint = document.getElementById('saveAsHint');

  /* 填「保存到」下拉：工作区里已有的目录 */
  function fillSaveDirs(selected) {
    saveAsDir.innerHTML = '';
    api('/api/ide/list').then(function (d) {
      var dirs = (d.dirs && d.dirs.length) ? d.dirs : [''];
      dirs.forEach(function (x) {
        var o = document.createElement('option');
        o.value = x;
        o.textContent = x ? (d.workspace + '/' + x) : (d.workspace + '/（根目录）');
        saveAsDir.appendChild(o);
      });
      var want = (selected === undefined || selected === null) ? (d.defaultDir || '') : selected;
      if (dirs.indexOf(want) >= 0) saveAsDir.value = want;
    }).catch(function () {
      var o = document.createElement('option');
      o.value = '';
      o.textContent = state.workspace;
      saveAsDir.appendChild(o);
    });
  }

  function openSaveDialog(defaultName) {
    saveAsName.value = defaultName || 'untitled.py';
    saveAsMsg.textContent = '';
    saveAsRemember.checked = false;
    saveAsHint.textContent = '当前工作区：' + state.workspace;
    fillSaveDirs(state.defaultDir || '');
    dlgSaveAs.showModal();
  }

  /* 目录 + 文件名 → 资料根相对路径 */
  function composeTarget() {
    var dir = (saveAsDir.value || '').replace(/^\/+|\/+$/g, '');
    var name = saveAsName.value.trim().replace(/\\/g, '/').replace(/^\/+/, '');
    if (!name) return '';
    return state.workspace + '/' + (dir ? dir + '/' : '') + name;
  }

  function doSave(targetPath) {
    return api('/api/ide/save', { path: targetPath, content: state.editor.getValue() })
      .then(function (res) {
        state.path = res.path;
        state.name = res.name;
        state.savedValue = state.editor.getValue();
        state.dirty = false;
        history.replaceState(null, '', '/ide?path=' + encodeURIComponent(state.path));
        refreshTitle();
        refreshSaveBtn();
        setBadge(inWorkspace(state.path) ? '已保存' : '可编辑', 'ok');
        setTimeout(function () { refreshBadgeIdle(); }, 1200);
        return res;
      });
  }

  function saveFlow() {
    if (!state.enabled || !state.editor) return Promise.resolve(null);
    if (inWorkspace(state.path)) {
      return doSave(state.path).catch(function (e) {
        showOutput('保存失败', e.message, 'bad');
        return Promise.reject(e);
      });
    }
    // 课程文件：弹「保存到哪」对话框，等它结束再返回
    return new Promise(function (resolve) {
      saveAsResolve = resolve;
      openSaveDialog(state.path.split('/').pop() || 'untitled.py');
    });
  }

  var saveAsResolve = null;

  dlgSaveAs.addEventListener('close', function () {
    if (dlgSaveAs.returnValue !== 'save') {
      if (saveAsResolve) { saveAsResolve(null); saveAsResolve = null; }
      return;
    }
    var target = composeTarget();
    if (!target) {
      saveAsMsg.textContent = '请填写文件名';
      dlgSaveAs.showModal();
      return;
    }
    var dir = saveAsDir.value || '';
    doSave(target).then(function (res) {
      if (saveAsRemember.checked) {
        api('/api/ide/config', { defaultDir: dir })
          .then(function (s) { state.defaultDir = s.defaultDir || ''; })
          .catch(function () {});
      }
      if (saveAsResolve) { saveAsResolve(res); saveAsResolve = null; }
    }).catch(function (e) {
      saveAsMsg.textContent = e.message;
      dlgSaveAs.showModal();
    });
  });

    el.btnSave.addEventListener('click', saveFlow);

  el.btnSaveAs.addEventListener('click', function () {
    if (!state.editor) return;
    openSaveDialog(state.path.split('/').pop() || 'untitled.py');
  });

  /* ---------- 运行 ---------- */
  el.btnRun.addEventListener('click', function () {
    if (!state.enabled) return;
    var pre = Promise.resolve(null);
    // 有未保存改动：能保存就先保存，不能保存就用磁盘上的原版
    if (state.dirty && inWorkspace(state.path)) pre = saveFlow();
    pre.then(function () {
      showOutput('运行中…', '', '');
      return api('/api/ide/run', { path: state.path });
    }).then(function (res) {
      if (res && res.error) { showOutput('运行失败', res.error, 'bad'); return; }
      var title = (res.timedOut ? '超时（' + res.timeout + 's）被杀' : 'exit ' + res.code)
        + ' · ' + res.ms + 'ms'
        + (res.truncated ? ' · 输出已截断' : '');
      var text = '';
      if (res.stdout) text += res.stdout;
      if (res.stderr) text += (text ? '\n' : '') + res.stderr;
      showOutput(title, text, res.code === 0 && !res.timedOut ? 'ok' : 'bad');
    }).catch(function (e) {
      showOutput('运行失败', e.message, 'bad');
    });
  });

  /* ---------- 设置 ---------- */
  var dlgSettings = document.getElementById('dlgSettings');
  var cfgWorkspace = document.getElementById('cfgWorkspace');
  var cfgPython = document.getElementById('cfgPython');
  var cfgTimeout = document.getElementById('cfgTimeout');
  var cfgMsg = document.getElementById('cfgMsg');
  var cfgPythonHint = document.getElementById('cfgPythonHint');
  var cfgExtraPaths = document.getElementById('cfgExtraPaths');
  var cfgLangs = document.getElementById('cfgLangs');
  var cfgLibs = document.getElementById('cfgLibs');
  var cfgLibInput = document.getElementById('cfgLibInput');
  var cfgLibHint = document.getElementById('cfgLibHint');
  var btnLibInstall = document.getElementById('btnLibInstall');
  var btnLibClear = document.getElementById('btnLibClear');

  /* 语言列表：只读展示，装/卸交给 agent 或 plugins/ 目录 */
  function renderLangs(list, errors) {
    if (!cfgLangs) return;
    cfgLangs.innerHTML = '';
    (list || []).forEach(function (lang) {
      var row = document.createElement('div');
      row.className = 'cfg-lang' + (lang.available ? '' : ' is-off');
      var name = document.createElement('b');
      name.textContent = lang.name;
      var meta = document.createElement('span');
      meta.textContent = lang.ext.join(' ') + (lang.twoStage ? ' · 两段式' : '');
      var state_ = document.createElement('em');
      state_.textContent = lang.available ? '可用' : '缺 ' + (lang.missing || []).join('/');
      row.appendChild(name);
      row.appendChild(meta);
      row.appendChild(state_);
      cfgLangs.appendChild(row);
    });
    (errors || []).forEach(function (msg) {
      var row = document.createElement('div');
      row.className = 'cfg-lang is-bad';
      row.textContent = '插件有问题：' + msg;
      cfgLangs.appendChild(row);
    });
  }

  function renderLibs(info) {
    if (!cfgLibs) return;
    var list = (info && info.packages) || [];
    var kb = Math.round(((info && info.bytes) || 0) / 1024);
    cfgLibs.innerHTML = '';
    var head = document.createElement('div');
    head.className = 'cfg-libs-head';
    head.textContent = list.length
      ? '已装 ' + list.length + ' 个，共 ' + kb + ' KB'
      : '空的（系统里已有的包不用放进来）';
    cfgLibs.appendChild(head);
    list.forEach(function (p) {
      var row = document.createElement('div');
      row.className = 'cfg-lib';
      row.textContent = p.name + ' ' + p.version;
      cfgLibs.appendChild(row);
    });
  }

  function loadLibInfo() {
    return api('/api/ide/pylibs').then(function (info) {
      renderLibs(info);
      return info;
    });
  }

  el.btnSettings.addEventListener('click', function () {
    cfgWorkspace.value = state.workspace;
    cfgPython.value = state.pythonCustom ? state.python : '';
    cfgTimeout.value = state.timeout;
    if (cfgExtraPaths) cfgExtraPaths.value = (state.extraPaths || []).join('\n');
    cfgMsg.textContent = '';
    cfgPythonHint.textContent = '当前生效：' + state.python;
    renderLangs(state.languages, state.languageErrors);
    if (cfgLibHint) cfgLibHint.textContent = '';
    loadLibInfo().catch(function () {});
    dlgSettings.showModal();
  });

  var LABEL_OK = 'ok';
  if (btnLibInstall) {
    btnLibInstall.addEventListener('click', function () {
      var names = (cfgLibInput.value || '').trim();
      if (!names) { cfgLibHint.textContent = '先填包名'; return; }
      btnLibInstall.disabled = true;
      cfgLibHint.textContent = '安装中…（会先检查系统里有没有）';
      api('/api/ide/pylibs', { packages: names }).then(function (res) {
        renderLibs(res);
        var parts = [];
        if (res.installed && res.installed.length) parts.push('新装：' + res.installed.join(', '));
        if (res.skipped && res.skipped.length) parts.push('跳过：' + res.skipped.join(', '));
        cfgLibHint.textContent = parts.join('；') || '完成';
        cfgLibInput.value = '';
      }).catch(function (e) {
        cfgLibHint.textContent = '失败：' + e.message;
      }).then(function () { btnLibInstall.disabled = false; });
    });
  }
  if (btnLibClear) {
    btnLibClear.addEventListener('click', function () {
      if (!window.confirm('清空私有库目录？（系统解释器里的包不受影响）')) return;
      api('/api/ide/pylibs/clear', {}).then(function (res) {
        renderLibs(res);
        cfgLibHint.textContent = '已清空';
      }).catch(function (e) { cfgLibHint.textContent = '失败：' + e.message; });
    });
  }

  dlgSettings.addEventListener('close', function () {
    if (dlgSettings.returnValue !== 'save') return;
    cfgMsg.textContent = '';
    api('/api/ide/config', {
      workspace: cfgWorkspace.value,
      python: cfgPython.value,
      timeout: cfgTimeout.value,
      extraPaths: (cfgExtraPaths && cfgExtraPaths.value) ? cfgExtraPaths.value : ''
    }).then(function (s) {
      state.workspace = s.workspace;
      state.workspaceAbs = s.workspaceAbs;
      state.python = s.python;
      state.pythonCustom = s.pythonCustom;
      state.timeout = s.timeout;
      state.extraPaths = s.extraPaths || [];
      state.languages = s.languages || [];
      state.languageErrors = s.languageErrors || [];
      refreshSaveBtn();
      refreshBadgeIdle();
      showOutput('设置已保存', '工作区：' + s.workspace + '\n解释器：' + s.python + '\n超时：' + s.timeout + 's'
        + '\n额外路径：' + (state.extraPaths.length ? state.extraPaths.join(' , ') : '（无）')
        + '\n语言：' + state.languages.filter(function (l) { return l.available; }).map(function (l) { return l.id; }).join(', '), LABEL_OK);
    }).catch(function (e) {
      cfgMsg.textContent = e.message;
      dlgSettings.showModal();
    });
  });

  /* ---------- 快捷键 ---------- */
  document.addEventListener('keydown', function (e) {
    if (!(e.ctrlKey || e.metaKey)) return;
    if (e.key === 's') { e.preventDefault(); saveFlow(); }
    else if (e.key === 'Enter') { e.preventDefault(); el.btnRun.click(); }
  });

  /* ---------- 启动 ---------- */
  function refreshBadgeIdle() {
    if (!state.enabled) { setBadge('IDE 未启用', 'bad'); return; }
    if (state.dirty) { setBadge('未保存', 'warn'); return; }
    setBadge(inWorkspace(state.path) ? '工作区' : '课程文件 · 只读', '');
  }

  applyTheme(preferredTheme());

  api('/api/ide/status').then(function (st) {
    state.enabled = !!st.enabled;
    state.workspace = st.workspace || '';
    state.defaultDir = st.defaultDir || '';
    state.workspaceAbs = st.workspaceAbs || '';
    state.python = st.python || '';
    state.pythonCustom = !!st.pythonCustom;
    state.timeout = st.timeout || 10;
    state.extraPaths = st.extraPaths || [];
    state.languages = st.languages || [];
    state.languageErrors = st.languageErrors || [];

    if (!st.enabled) {
      fail('IDE 未启用。停止服务后加 --ide 重启：\n\npython server.py --ide');
      return;
    }
    if (!state.path) {
      renderWorkspace();
      return;
    }

    window.MonacoEnvironment = {
      getWorkerUrl: function () { return '/static/vendor/monaco/vs/base/worker/workerMain.js'; }
    };
    require.config({ paths: { vs: '/static/vendor/monaco/vs' } });
    require(['vs/editor/editor.main'], openFile);
  }).catch(function (e) {
    fail('读取 IDE 状态失败：' + e.message);
  });

  function openFile() {
    fetch('/api/file?path=' + encodeURIComponent(state.path), { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (file) {
        if (file && file.error) { return fail('打开失败：' + file.error); }
        state.name = file.name || state.path;
        if (file.content === null || file.content === undefined) {
          return fail('这个文件不能当文本编辑：' + (file.reason || '过大或二进制'));
        }
        state.savedValue = file.content;
        state.editor = monaco.editor.create(el.host, {
          value: file.content,
          language: LANG[file.language] || 'plaintext',
          theme: document.body.classList.contains('dark') ? 'vs-dark' : 'vs',
          automaticLayout: true,
          fontSize: 13.5,
          lineHeight: 21,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          renderWhitespace: 'selection',
          tabSize: 4,
          padding: { top: 10 }
        });
        state.editor.onDidChangeModelContent(function () {
          var dirty = state.editor.getValue() !== state.savedValue;
          if (dirty !== state.dirty) {
            state.dirty = dirty;
            refreshTitle();
            refreshBadgeIdle();
          }
        });
        state.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, function () { saveFlow(); });
        state.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, function () { el.btnRun.click(); });

        el.mask.hidden = true;
        el.btnNew.hidden = true;
        el.btnRun.disabled = false;
        el.btnSaveAs.disabled = false;
        refreshTitle();
        refreshSaveBtn();
        refreshBadgeIdle();
      })
      .catch(function (e) { fail('加载失败：' + (e && e.message ? e.message : e)); });
  }
})();
