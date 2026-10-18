/* =====================================================================
   StudyAI 渲染器
   - Markdown（含公式保护、相对图片路径解析、代码高亮、TOC）
   - Notebook（markdown + code + outputs，含内嵌图片）
   - 代码 / 纯文本 / PDF / 图片 / HTML / 不可渲染降级
   ===================================================================== */
(function (global) {
  'use strict';

  /* ---------- 常量 ---------- */
  var PUA_A = '\uE000', PUA_B = '\uE001';   // 私有区字符做占位符，Markdown 不会动
  var CODE_LANGS = null;

  /* ---------- 工具 ---------- */
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function humanSize(n) {
    if (n == null) return '';
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
    if (n < 1073741824) return (n / 1048576).toFixed(1) + ' MB';
    return (n / 1073741824).toFixed(2) + ' GB';
  }

  /* 把相对路径解析为相对 ROOT 的路径 */
  function resolvePath(baseDir, rel) {
    if (!rel) return '';
    if (/^(https?:|data:|blob:|mailto:|#|\/\/)/i.test(rel)) return rel;
    var p = rel.replace(/\\/g, '/');
    if (p.charAt(0) === '/') return p.slice(1);          // 以 ROOT 为根的绝对路径
    var parts = (baseDir ? baseDir.split('/') : []).concat(p.split('/'));
    var out = [];
    for (var i = 0; i < parts.length; i++) {
      var seg = parts[i];
      if (seg === '' || seg === '.') continue;
      if (seg === '..') { out.pop(); continue; }
      out.push(seg);
    }
    return out.join('/');
  }

  function rawUrl(rootRelPath) {
    return '/api/raw?path=' + encodeURIComponent(rootRelPath);
  }

  /* 按真实目录结构访问文件 —— HTML 多页站点靠相对链接导航时必须用这个。
     用 /api/raw?path=... 会因为浏览器解析相对URL时丢弃 query 而失效。 */
  function fileUrl(rootRelPath) {
    return '/files/' + String(rootRelPath).split('/').map(encodeURIComponent).join('/');
  }

  /* 去掉 <script>、on* 属性，防止 notebook 输出里的脚本执行 */
  function sanitizeHTML(html) {
    return String(html)
      .replace(/<script[\s\S]*?<\/script>/gi, '')
      .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
      .replace(/\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '')
      .replace(/javascript:/gi, '');
  }

  /* =================================================================
     Markdown
     ================================================================= */

  /* 1) 抽出围栏代码块，避免内部内容被当作公式/强调处理 */
  function protectCode(md, store) {
    return md.replace(/^([ \t]*)(```+|~~~+)([^\n]*)\n([\s\S]*?)\n?\1\2[ \t]*$/gm,
      function (m, indent, fence, info, body) {
        var lang = (info || '').trim().split(/\s+/)[0] || '';
        store.code.push({ lang: lang, body: body });
        return PUA_A + 'C' + (store.code.length - 1) + PUA_B;
      });
  }

  /* 2) 抽出数学公式（$$..$$ / \[..\] / $..$ / \(..\)） */
  function protectMath(md, store) {
    // 先处理块级（跨行）
    md = md.replace(/\$\$([\s\S]+?)\$\$/g, function (m, tex) {
      store.math.push({ tex: tex, display: true });
      return PUA_A + 'M' + (store.math.length - 1) + PUA_B;
    });
    md = md.replace(/\\\[([\s\S]+?)\\\]/g, function (m, tex) {
      store.math.push({ tex: tex, display: true });
      return PUA_A + 'M' + (store.math.length - 1) + PUA_B;
    });
    // 行内：$ 不跨行，且两侧不能是数字/空白（降低误判）
    // 注意：中间的 *? 必须可省，否则 $V$ / $A$ 这类单字符公式匹配不到
    //（AFA 教材大量使用单字母记法，旧写法会漏掉它们）
    md = md.replace(/(^|[^\w\\$])\$([^\s$](?:[^$\n]*?[^\s$\\])?)\$(?!\d)/g,
      function (m, pre, tex) {
        if (/\d/.test(pre) && /^\d/.test(tex)) return m;   // $5$ 这类价格不处理
        store.math.push({ tex: tex, display: false });
        return pre + PUA_A + 'M' + (store.math.length - 1) + PUA_B;
      });
    md = md.replace(/\\\(([\s\S]+?)\\\)/g, function (m, tex) {
      store.math.push({ tex: tex, display: false });
      return PUA_A + 'M' + (store.math.length - 1) + PUA_B;
    });
    return md;
  }

  /* 3) 回填占位符 */
  function restore(html, store, baseDir) {
    // 代码块
    html = html.replace(new RegExp(PUA_A + 'C(\\d+)' + PUA_B, 'g'), function (m, i) {
      var c = store.code[+i];
      if (!c) return '';
      var langCls = c.lang ? ' class="language-' + esc(c.lang) + '"' : '';
      return '<pre><code' + langCls + '>' + esc(c.body) + '</code></pre>';
    });
    // 定理环境：必须在「公式还原」之前插入。
    // 否则块内那些公式占位符还躺在 store.thm 里，主 html 上还原公式时看不见它们，
    // 结果定理框里会露出 PUA 占位符。
    if (store.thm && store.thm.length) {
      html = html.replace(/<!--THM(\d+)-->/g, function (m, i) {
        return store.thm[+i] || '';
      });
    }
    // 公式
    html = html.replace(new RegExp(PUA_A + 'M(\\d+)' + PUA_B, 'g'), function (m, i) {
      var mm = store.math[+i];
      if (!mm) return '';
      try {
        return global.katex.renderToString(mm.tex, {
          displayMode: mm.display, throwOnError: false, strict: false,
          trust: false, output: 'html'
        });
      } catch (e) {
        return '<code class="math-error">' + esc(mm.tex) + '</code>';
      }
    });
    // 图片相对路径
    html = html.replace(/(<img\b[^>]*?\ssrc=)(["'])(.*?)\2/gi, function (m, pre, q, src) {
      if (/^(https?:|data:|blob:)/i.test(src)) return m;
      var abs = resolvePath(baseDir, src);
      return pre + q + rawUrl(abs) + q + ' data-src="' + esc(src) + '" loading="lazy"';
    });
    // 链接：站内相对链接转 hash 路由
    html = html.replace(/(<a\b[^>]*?\shref=)(["'])(?!https?:|mailto:|#|\/api\/)(.*?)\2/gi,
      function (m, pre, q, href) {
        var abs = resolvePath(baseDir, href.split('#')[0]);
        if (!abs) return m;
        return pre + q + '#/' + encodeURI(abs) + q + ' data-internal="1"';
      });
    return html;
  }

  /* 配置 marked —— 允许不同版本/构建方式，缺失 Renderer 时降级而非崩溃 */
  var markedReady = false;
  function initMarked() {
    if (markedReady) return;
    var M = global.marked;
    if (!M) throw new Error('marked 未加载');

    var opts = { gfm: true, breaks: false, headerIds: true, mangle: false };

    try {
      if (typeof M.Renderer === 'function') {
        var renderer = new M.Renderer();
        var origLink = renderer.link ? renderer.link.bind(renderer) : null;
        if (origLink) {
          renderer.link = function (href, title, text) {
            var out = origLink(href, title, text);
            // 外链新窗口打开
            if (/^https?:/i.test(href || '')) {
              out = out.replace('<a ', '<a target="_blank" rel="noopener noreferrer" ');
            }
            return out;
          };
        }
        opts.renderer = renderer;
      }
    } catch (e) {
      // Renderer 不可用时忽略，仍能用默认渲染器
      if (global.console && console.warn) console.warn('marked.Renderer 不可用，使用默认渲染:', e.message);
    }

    if (typeof M.setOptions === 'function') M.setOptions(opts);
    else if (typeof M.use === 'function') M.use(opts);

    if (typeof M.parse !== 'function' && typeof M.marked !== 'function') {
      throw new Error('marked 没有可用的 parse 方法');
    }
    markedReady = true;
  }

  /* 兼容不同 marked 版本的解析入口 */
  function mdParse(md) {
    var M = global.marked;
    if (typeof M.parse === 'function') return M.parse(md);
    if (typeof M.marked === 'function') return M.marked(md);
    throw new Error('无法调用 marked 解析');
  }

  /* =================================================================
     定理环境（::: definition / ::: theorem / ::: proof ...）
     AFA 教材用了 188 个这种 Pandoc 风格的分块指令。
     配色对齐 build_docx.py 的 BOX 表，保证网页与 PDF 观感一致。
     ================================================================= */
  var DIRECTIVE_KIND = {
    definition:  { label: '定义', cls: 'def' },
    theorem:     { label: '定理', cls: 'thm' },
    lemma:       { label: '引理', cls: 'thm' },
    corollary:   { label: '推论', cls: 'thm' },
    proposition: { label: '命题', cls: 'thm' },
    example:     { label: '例',   cls: 'ex' },
    remark:      { label: '注',   cls: 'rem' },
    note:        { label: '注',   cls: 'rem' },
    proof:       { label: '证明', cls: 'proof' },
    reading:     { label: '延伸阅读', cls: 'read' },
    history:     { label: '历史', cls: 'read' },
    algorithm:   { label: '算法', cls: 'algo' }
  };

  /* 把 ::: 块换成 HTML 注释占位，块内正文照常走 marked */
  function protectDirectives(md, store) {
    if (!store.thm) store.thm = [];
    var lines = md.split('\n');
    var out = [];
    var i = 0;
    while (i < lines.length) {
      var m = /^:::[ \t]*([A-Za-z]+)[ \t]*(.*)$/.exec(lines[i]);
      if (!m) { out.push(lines[i]); i++; continue; }

      var kind = m[1].toLowerCase();
      var title = (m[2] || '').trim();
      var body = [];
      i++;
      while (i < lines.length && !/^:::[ \t]*$/.test(lines[i])) { body.push(lines[i]); i++; }
      if (i < lines.length) i++;   // 吃掉闭合的 :::

      var meta = DIRECTIVE_KIND[kind] || { label: kind, cls: 'rem' };
      var inner = mdParse(body.join('\n'));
      var head = title
        ? '<div class="thm-head">' + esc(title) + '</div>'
        : '<div class="thm-head"><span class="thm-kind">' + esc(meta.label) + '</span></div>';

      store.thm.push(
        '<div class="thm thm-' + meta.cls + '" data-kind="' + esc(kind) + '">' +
        head + '<div class="thm-body">' + inner + '</div></div>'
      );
      out.push('<!--THM' + (store.thm.length - 1) + '-->');
      out.push('');
    }
    return out.join('\n');
  }

  /* 主入口：Markdown → { html, toc } */
  function renderMarkdown(text, baseDir) {
    initMarked();
    var store = { code: [], math: [], thm: [] };
    var md = String(text || '').replace(/\r\n/g, '\n');
    // Jupyter Book / MyST 的 [TOC] 占位指令：应用已提供右侧目录，直接移除
    md = md.replace(/^[ \t]*\[TOC\][ \t]*$/gim, '');
    md = protectCode(md, store);
    md = protectMath(md, store);
    md = protectDirectives(md, store);
    var html = mdParse(md);
    html = restore(html, store, baseDir);

    // 生成 TOC
    var toc = [];
    html = html.replace(/<h([1-4])\b([^>]*)>([\s\S]*?)<\/h\1>/g,
      function (m, lv, attrs, inner) {
        var idm = /id="([^"]+)"/.exec(attrs);
        var id = idm ? idm[1] : 'h-' + toc.length;
        if (!idm) attrs += ' id="' + id + '"';
        var plain = inner.replace(/<[^>]+>/g, '').trim();
        if (plain) toc.push({ level: +lv, id: id, text: plain });
        return '<h' + lv + attrs + '>' + inner + '</h' + lv + '>';
      });
    return { html: html, toc: toc };
  }

  /* =================================================================
     Notebook
     ================================================================= */
  function cellSource(src) {
    if (Array.isArray(src)) return src.join('');
    return String(src == null ? '' : src);
  }

  function renderOutputs(outputs, baseDir) {
    if (!outputs || !outputs.length) return '';
    var parts = [];
    for (var i = 0; i < outputs.length; i++) {
      var o = outputs[i];
      var t = o.output_type;

      if (t === 'stream') {
        var txt = cellSource(o.text);
        var isErr = o.name === 'stderr';
        parts.push('<div class="nb-out"><pre' + (isErr ? ' class="stderr"' : '') + '>'
          + esc(txt) + '</pre></div>');

      } else if (t === 'error') {
        var tb = (o.traceback || []).join('\n');
        parts.push('<div class="nb-out"><pre class="stderr">' + esc(tb || (o.ename + ': ' + o.evalue)) + '</pre></div>');

      } else if (t === 'execute_result' || t === 'display_data') {
        var d = o.data || {};
        var chunk = '';
        if (d['image/png']) {
          chunk += '<img src="data:image/png;base64,' + d['image/png'].toString().replace(/\s/g, '') + '" loading="lazy">';
        }
        if (d['image/jpeg']) {
          chunk += '<img src="data:image/jpeg;base64,' + d['image/jpeg'].toString().replace(/\s/g, '') + '" loading="lazy">';
        }
        if (d['image/svg+xml']) {
          chunk += '<div class="html-out">' + sanitizeHTML(cellSource(d['image/svg+xml'])) + '</div>';
        }
        if (d['text/html']) {
          chunk += '<div class="html-out">' + sanitizeHTML(cellSource(d['text/html'])) + '</div>';
        }
        if (!chunk && d['text/plain']) {
          chunk += '<pre>' + esc(cellSource(d['text/plain'])) + '</pre>';
        }
        if (chunk) parts.push('<div class="nb-out">' + chunk + '</div>');
      }
    }
    return parts.join('');
  }

  function renderNotebook(text, baseDir) {
    var nb;
    try { nb = JSON.parse(text); }
    catch (e) { throw new Error('Notebook JSON 解析失败: ' + e.message); }

    var cells = nb.cells || [];
    var meta = nb.metadata || {};
    var km = meta.kernelspec || {};
    var lm = meta.language_info || {};
    var lang = (lm.name || km.language || 'python').toLowerCase();

    var html = [];
    var codeIdx = 0;

    for (var i = 0; i < cells.length; i++) {
      var c = cells[i];
      var src = cellSource(c.source);

      if (c.cell_type === 'markdown') {
        var r = renderMarkdown(src, baseDir);
        html.push('<div class="nb-cell md">' + r.html + '</div>');

      } else if (c.cell_type === 'code') {
        codeIdx++;
        var outHtml = renderOutputs(c.outputs, baseDir);
        html.push(
          '<div class="nb-cell code">' +
            '<div class="nb-head"><span class="nb-prompt">In [' +
              (c.execution_count == null ? ' ' : c.execution_count) +
            ']:</span><span>代码</span><span class="nb-idx">#' + codeIdx + '</span></div>' +
            '<div class="nb-body"><pre><code class="language-' + esc(lang) + '">' +
              esc(src) + '</code></pre></div>' +
            (outHtml || '<div class="nb-empty">（无输出）</div>') +
          '</div>');
      } else if (src.trim()) {
        html.push('<div class="nb-cell"><div class="nb-head"><span>RAW</span></div>' +
          '<div class="nb-body"><pre><code>' + esc(src) + '</code></pre></div></div>');
      }
    }

    return {
      html: html.join(''),
      toc: [],
      meta: { cells: cells.length, codeCells: codeIdx,
              kernel: km.display_name || km.name || '未知',
              language: lang,
              nbformat: (nb.nbformat || '?') + '.' + (nb.nbformat_minor || 0) }
    };
  }

  /* =================================================================
     代码 / 文本
     ================================================================= */
  function renderCode(text, lang) {
    var language = lang && global.hljs.getLanguage(lang) ? lang : null;
    var html;
    try {
      if (language) {
        html = global.hljs.highlight(text, { language: language, ignoreIllegals: true }).value;
      } else {
        html = global.hljs.highlightAuto(text).value;
      }
    } catch (e) {
      html = esc(text);
    }
    var lines = String(text).split('\n').length;
    return {
      html: '<div class="nb-cell"><div class="nb-head"><span>' +
            esc(lang || 'text') + '</span><span class="nb-idx">' + lines + ' 行</span></div>' +
            '<div class="nb-body"><pre><code class="hljs">' + html + '</code></pre></div></div>',
      toc: []
    };
  }

  function renderText(text) {
    return { html: '<div class="nb-cell"><div class="nb-body"><pre><code>' +
             esc(text) + '</code></pre></div></div>', toc: [] };
  }

  /* =================================================================
     图片 / PDF / HTML / 降级
     ================================================================= */
  function renderImage(file) {
    var url = rawUrl(file.path);
    return {
      html: '<div class="img-view"><img src="' + url + '" alt="' + esc(file.name) + '">' +
            '<div class="imgbar"><span>' + esc(file.name) + '</span>' +
            '<span>' + humanSize(file.size) + '</span>' +
            '<span>点击图片可放大</span></div></div>',
      toc: []
    };
  }

  function renderPdf(file) {
    return {
      html: '<iframe class="pdf-view" src="' + rawUrl(file.path) + '#view=FitH"></iframe>',
      toc: []
    };
  }

  function renderHtmlFile(file) {
    // HTML 用 /files/ 按真实目录提供，页内相对链接（多页站点导航）才能正常解析。
    // sandbox 不给 allow-scripts：课程讲义是纯静态的，禁用脚本更安全。
    return {
      html: '<iframe class="html-view" sandbox="allow-same-origin" src="' +
            fileUrl(file.path) + '"></iframe>',
      toc: []
    };
  }

  function renderFallback(file, reason) {
    var p = file.path || '';
    return {
      html:
        '<div class="noview">' +
          '<div class="nv-ico">📦</div>' +
          '<h3>这个文件无法在浏览器里查看</h3>' +
          '<p>' + esc(reason || '二进制文件或体积过大') + '</p>' +
          '<div class="nv-path" data-copy="' + esc(p) + '" title="点击复制路径">' +
            esc(p) + '</div>' +
          '<p style="font-size:12.5px">复制路径后可在资源管理器或对应程序中打开</p>' +
        '</div>',
      toc: []
    };
  }

  /* =================================================================
     统一入口
     ================================================================= */
  function render(file) {
    var baseDir = file.path.split('/').slice(0, -1).join('/');
    var kind = file.kind;
    var text = file.content;

    if (file.reason) return renderFallback(file, file.reason);

    switch (kind) {
      case 'markdown':
        if (text == null) return renderFallback(file, '内容读取失败');
        var r = renderMarkdown(text, baseDir);
        return { html: r.html, toc: r.toc, type: 'markdown' };

      case 'notebook':
        if (text == null) return renderFallback(file, '内容读取失败');
        var n = renderNotebook(text, baseDir);
        return { html: n.html, toc: [], type: 'notebook', nbMeta: n.meta };

      case 'code':
        if (text == null) return renderFallback(file, '内容读取失败');
        var c = renderCode(text, file.language);
        return { html: c.html, toc: [], type: 'code' };

      case 'text':
        if (text == null) return renderFallback(file, '内容读取失败');
        var t = renderText(text);
        return { html: t.html, toc: [], type: 'text' };

      case 'image':
        return Object.assign(renderImage(file), { type: 'image' });

      case 'pdf':
        return Object.assign(renderPdf(file), { type: 'pdf' });

      case 'html':
        return Object.assign(renderHtmlFile(file), { type: 'html' });

      default:
        return renderFallback(file, '未知或二进制类型：' + (file.ext || '无扩展名'));
    }
  }

  /* 渲染后处理：高亮 + 图片点击放大 */
  function postProcess(container) {
    container.querySelectorAll('pre code:not(.hljs)').forEach(function (el) {
      try {
        var lang = null;
        var cls = el.className || '';
        var m = /language-([\w+-]+)/.exec(cls);
        if (m && global.hljs.getLanguage(m[1])) lang = m[1];
        if (lang) {
          el.innerHTML = global.hljs.highlight(el.textContent, { language: lang, ignoreIllegals: true }).value;
        } else {
          el.innerHTML = global.hljs.highlightAuto(el.textContent).value;
        }
        el.classList.add('hljs');
      } catch (e) { /* 高亮失败就用纯文本 */ }
    });

    container.querySelectorAll('img').forEach(function (img) {
      img.style.cursor = 'zoom-in';
      img.addEventListener('click', function () {
        var box = document.createElement('div');
        box.className = 'lightbox';
        var big = document.createElement('img');
        big.src = img.src;
        box.appendChild(big);
        box.addEventListener('click', function () { box.remove(); });
        document.body.appendChild(box);
      });
      img.addEventListener('error', function () {
        img.alt = '⚠ 图片加载失败: ' + (img.getAttribute('data-src') || img.src);
        img.style.cssText = 'border:1px dashed var(--warn);padding:8px;opacity:.7;font-size:12px';
      });
    });
  }

  global.Renderers = {
    render: render,
    postProcess: postProcess,
    resolvePath: resolvePath,
    rawUrl: rawUrl,
    fileUrl: fileUrl,
    humanSize: humanSize,
    esc: esc,
    renderMarkdown: renderMarkdown
  };
})(window);
