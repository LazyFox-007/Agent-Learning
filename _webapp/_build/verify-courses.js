/* 验证 08-官方体系课程 里的图片相对路径能否被 renderers.js 正确解析到真实文件 */
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ROOT = 'C:\\StudyAI';
const VENDOR = 'C:\\StudyAI\\_webapp\\static\\vendor';
const sandbox = { console, setTimeout, clearTimeout };
sandbox.window = sandbox; sandbox.self = sandbox; sandbox.globalThis = sandbox;
sandbox.document = { querySelector: () => null, querySelectorAll: () => [] };
vm.createContext(sandbox);
['marked.min.js', 'katex.min.js', 'highlight.min.js'].forEach(f =>
  vm.runInContext(fs.readFileSync(path.join(VENDOR, f), 'utf8'), sandbox, { filename: f }));
vm.runInContext(fs.readFileSync('C:\\StudyAI\\_webapp\\static\\renderers.js', 'utf8'), sandbox);
const R = sandbox.window.Renderers;

const SEC = path.join(ROOT, '08-官方体系课程');

// 收集待验证的 markdown：每个课程取前 3 个
const targets = [];
for (const repo of fs.readdirSync(SEC)) {
  const rp = path.join(SEC, repo);
  if (!fs.statSync(rp).isDirectory()) continue;
  // 微软课程：translations/zh-CN/<lesson>/README.md
  const zh = path.join(rp, 'translations', 'zh-CN');
  if (fs.existsSync(zh)) {
    const entries = fs.readdirSync(zh).filter(n => fs.statSync(path.join(zh, n)).isDirectory());
    entries.slice(0, 4).forEach(les => {
      const f = path.join(zh, les, 'README.md');
      if (fs.existsSync(f)) targets.push(f);
    });
    const top = path.join(zh, 'README.md');
    if (fs.existsSync(top)) targets.push(top);
  }
  // HF 课程：chapters/<lang>/<n>.md
  const ch = path.join(rp, 'chapters');
  if (fs.existsSync(ch)) {
    const langs = fs.readdirSync(ch).filter(n => fs.statSync(path.join(ch, n)).isDirectory());
    for (const lg of langs.slice(0, 3)) {
      const files = fs.readdirSync(path.join(ch, lg)).filter(f => f.endsWith('.md')).slice(0, 2);
      files.forEach(f => targets.push(path.join(ch, lg, f)));
    }
  }
  // llm-course: README.md
  const rm = path.join(rp, 'README.md');
  if (fs.existsSync(rm)) targets.push(rm);
}

console.log('待验文件数: ' + targets.length + '\n');

let totalImg = 0, okImg = 0, badImg = 0;
const badList = [];
const seen = new Set();

for (const f of targets) {
  const rel = path.relative(ROOT, f).replace(/\\/g, '/');
  if (seen.has(rel)) continue;
  seen.add(rel);
  const baseDir = rel.split('/').slice(0, -1).join('/');
  const text = fs.readFileSync(f, 'utf8');

  // 用真实渲染管线
  let out;
  try { out = R.renderMarkdown(text, baseDir); }
  catch (e) { console.log('[渲染异常] ' + rel + ' : ' + e.message); continue; }

  const srcs = [...out.html.matchAll(/<img[^>]*\ssrc="\/api\/raw\?path=([^"]+)"/g)]
                 .map(m => decodeURIComponent(m[1]));
  let localOk = 0, localBad = 0;
  for (const s of srcs) {
    totalImg++;
    const abs = path.join(ROOT, s.replace(/\//g, '\\'));
    if (fs.existsSync(abs)) { okImg++; localOk++; }
    else { badImg++; localBad++; if (badList.length < 8) badList.push(rel + '  ->  ' + s); }
  }
  const mark = localBad === 0 ? 'OK  ' : 'BAD ';
  console.log('[' + mark + '] ' + String(srcs.length).padStart(2) + ' 图  ' + rel);
}

console.log('\n' + '='.repeat(64));
console.log('  图片引用总数 : ' + totalImg);
console.log('  解析成功     : ' + okImg);
console.log('  解析失败     : ' + badImg);
console.log('='.repeat(64));
if (badList.length) {
  console.log('\n失败样例:');
  badList.forEach(b => console.log('  ' + b));
}
process.exit(badImg > 0 ? 1 : 0);
