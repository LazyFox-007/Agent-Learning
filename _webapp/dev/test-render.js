/* 渲染管线测试：用 Node 直接驱动 renderers.js，检查输出 HTML */
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const NM = 'C:\\StudyAI\\_webapp\\_build\\node_modules';

// 搭一个最小 DOM 环境（模拟浏览器 <script> 加载，而非 Node require）
const sandbox = { console, setTimeout, clearTimeout };
sandbox.window = sandbox;
sandbox.self = sandbox;
sandbox.globalThis = sandbox;
sandbox.document = { querySelector: () => null, querySelectorAll: () => [] };
vm.createContext(sandbox);

// 用与浏览器一致的方式依次加载 vendor 库
const VENDOR = 'C:\\StudyAI\\_webapp\\static\\vendor';
['marked.min.js', 'katex.min.js', 'highlight.min.js'].forEach(function (f) {
  const code = fs.readFileSync(path.join(VENDOR, f), 'utf8');
  vm.runInContext(code, sandbox, { filename: f });
});

console.log('库加载检查:');
console.log('  window.marked :', typeof sandbox.marked,
            '| Renderer:', typeof (sandbox.marked && sandbox.marked.Renderer),
            '| parse:', typeof (sandbox.marked && sandbox.marked.parse),
            '| marked():', typeof (sandbox.marked && sandbox.marked.marked));
console.log('  window.katex  :', typeof sandbox.katex,
            '| renderToString:', typeof (sandbox.katex && sandbox.katex.renderToString));
console.log('  window.hljs   :', typeof sandbox.hljs,
            '| highlight:', typeof (sandbox.hljs && sandbox.hljs.highlight));

const src = fs.readFileSync('C:\\StudyAI\\_webapp\\static\\renderers.js', 'utf8');
vm.runInContext(src, sandbox, { filename: 'renderers.js' });
const R = sandbox.window.Renderers;
if (!R) { console.log('FATAL: Renderers 未挂载'); process.exit(1); }

let pass = 0, fail = 0;
function check(label, ok, extra) {
  (ok ? pass++ : fail++);
  console.log('  ' + (ok ? '[OK]  ' : '[FAIL]') + ' ' + label + (extra != null ? '  -> ' + extra : ''));
}

/* ---------------- 测试 1：Markdown + 公式保护 ---------------- */
console.log('\n=== 测试1: Markdown 渲染与公式保护 ===');

const md = [
  '# 一级标题',
  '',
  '行内公式 $a_i^2 + b_j$ 与价格 $5 应区分。',
  '',
  '块级公式：',
  '',
  '$$',
  '\\nabla_\\theta J(\\theta) = \\frac{1}{m} \\sum_{i=1}^{m} (h_\\theta(x^{(i)}) - y^{(i)}) x^{(i)}',
  '$$',
  '',
  '矩阵：',
  '',
  '$$A = \\begin{bmatrix} a_{11} & a_{12} \\\\ a_{21} & a_{22} \\end{bmatrix}$$',
  '',
  '```python',
  'x = 100  # cost $5 and $10',
  'name = f"{x}"',
  '```',
  '',
  '![测试图](../images/foo.png)',
  '',
  '[站内链接](./other.md)',
  '',
  '| 列A | 列B |',
  '|---|---|',
  '| 1 | 2 |',
].join('\n');

const r1 = R.renderMarkdown(md, '01-test/dir');
const h = r1.html;

check('KaTeX 渲染节点 >= 3', (h.match(/class="katex/g) || []).length >= 3,
      (h.match(/class="katex/g) || []).length + ' 个');
check('块级公式用 katex-display', h.includes('katex-display'));
check('无残留占位符', !h.includes('\uE000'));
check('代码块保留语言类', h.includes('language-python'));
check('代码块内 $ 未被当公式', !(h.split('language-python')[1] || '').split('</code>')[0].includes('katex'));
const imgSrc = (/<img[^>]*\ssrc="([^"]+)"/.exec(h) || [])[1] || '(未找到 img)';
const imgDecoded = imgSrc.replace(/^.*[?&]path=/, '').replace(/\+/g, ' ');
let imgPath = imgDecoded;
try { imgPath = decodeURIComponent(imgDecoded); } catch (e) {}
check('图片相对路径重写', h.includes('/api/raw?path=') && imgPath === '01-test/images/foo.png',
      imgSrc + '  =>  ' + imgPath);
check('图片保留原始 src 便于报错', h.includes('data-src="../images/foo.png"'));
check('站内链接转为 hash 路由', h.includes('#/01-test/dir/other.md'));
check('表格渲染', h.includes('<table>') && h.includes('<th>'));
check('TOC 提取', r1.toc.length >= 1, r1.toc.length + ' 条');
check('TOC 含正确标题', r1.toc.some(t => t.text.includes('一级标题')));

// 路径解析边界
check('resolvePath 上溯', R.resolvePath('a/b/c', '../../x/y.png') === 'a/x/y.png',
      R.resolvePath('a/b/c', '../../x/y.png'));
check('resolvePath 绝对', R.resolvePath('a/b', '/root.png') === 'root.png');
check('resolvePath 外链不动', R.resolvePath('a/b', 'https://x.com/i.png') === 'https://x.com/i.png');

/* ---------------- 测试 2：Notebook ---------------- */
console.log('\n=== 测试2: Notebook 渲染 ===');

const nb = {
  nbformat: 4, nbformat_minor: 5,
  metadata: { kernelspec: { display_name: 'Python 3', language: 'python' }, language_info: { name: 'python' } },
  cells: [
    { cell_type: 'markdown', metadata: {}, source: ['## 小节标题\n', '含公式 $E=mc^2$\n'] },
    { cell_type: 'code', execution_count: 1, metadata: {}, source: ['print("hello")\n', 'x = 1'],
      outputs: [
        { output_type: 'stream', name: 'stdout', text: ['hello\n'] },
        { output_type: 'execute_result', execution_count: 1, metadata: {}, data: { 'text/plain': ['42'] } }
      ] },
    { cell_type: 'code', execution_count: 2, metadata: {}, source: ['1/0'],
      outputs: [{ output_type: 'error', ename: 'ZeroDivisionError', evalue: 'division by zero',
                  traceback: ['Traceback (most recent call last)', 'ZeroDivisionError: division by zero'] }] },
    { cell_type: 'code', execution_count: 3, metadata: {}, source: ['plot()'],
      outputs: [{ output_type: 'display_data', metadata: {}, data: { 'image/png': 'iVBORw0KGgoAAAANSUhEUg==' } }] }
  ]
};

const r2 = R.render({
  path: '05-test/nb.ipynb', name: 'nb.ipynb', size: 1234, ext: '.ipynb',
  kind: 'notebook', language: 'python', renderable: true, content: JSON.stringify(nb)
});
const nh = r2.html;

check('markdown cell 含公式', nh.includes('katex'));
check('code cell 高亮类', nh.includes('language-python'));
check('stdout 输出', nh.includes('hello'));
check('execute_result', nh.includes('42'));
check('error 追踪', nh.includes('ZeroDivisionError'));
check('内嵌 base64 图片', nh.includes('data:image/png;base64'));
check('cell 数量 = 4', (nh.match(/nb-cell/g) || []).length === 4, (nh.match(/nb-cell/g) || []).length + ' 个');

// 脚本注入防护
const nbXss = {
  nbformat: 4, nbformat_minor: 5, metadata: {},
  cells: [{ cell_type: 'code', execution_count: 1, metadata: {}, source: ['x'],
    outputs: [{ output_type: 'display_data', metadata: {},
      data: { 'text/html': ['<script>alert(1)</script><img src=x onerror=alert(2)>'] } }] }]
};
const rX = R.render({ path: 'a/x.ipynb', name: 'x.ipynb', size: 10, ext: '.ipynb',
  kind: 'notebook', renderable: true, content: JSON.stringify(nbXss) });
check('notebook 输出过滤 <script>', !rX.html.includes('<script>'));
check('notebook 输出过滤 onerror', !/onerror\s*=/i.test(rX.html));

/* ---------------- 测试 3：代码 / 文本 ---------------- */
console.log('\n=== 测试3: 代码与文本 ===');
const r3 = R.render({ path: 'a/b.py', name: 'b.py', size: 40, ext: '.py', kind: 'code',
  language: 'python', renderable: true, content: 'import os\ndef f(x):\n    return x * 2' });
check('hljs 高亮生效', /class="hljs-/.test(r3.html));

const r3b = R.render({ path: 'a/c.txt', name: 'c.txt', size: 5, ext: '.txt', kind: 'text',
  renderable: true, content: 'plain text' });
check('纯文本转义', r3b.html.includes('plain text'));

/* ---------------- 测试 4：降级路径 ---------------- */
console.log('\n=== 测试4: 不可渲染降级 ===');
const r4 = R.render({ path: 'a/x.graffle', name: 'x.graffle', size: 999, ext: '.graffle',
  kind: 'binary', renderable: false });
check('降级提示框', r4.html.includes('noview'));
check('路径可复制', r4.html.includes('data-copy'));

const r5 = R.render({ path: 'a/big.md', name: 'big.md', size: 99999999, ext: '.md',
  kind: 'markdown', renderable: false, content: null, reason: '文件过大' });
check('超大文件降级', r5.html.includes('noview') && r5.html.includes('文件过大'));

/* ---------------- 汇总 ---------------- */
console.log('\n' + '='.repeat(52));
console.log('  通过 ' + pass + ' 项，失败 ' + fail + ' 项');
console.log('='.repeat(52));
process.exit(fail > 0 ? 1 : 0);
