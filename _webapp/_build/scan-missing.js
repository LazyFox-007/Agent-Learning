/* 全量扫描 08-官方体系课程 的中文 markdown，列出所有解析不到的图片引用 */
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

function walk(dir, acc) {
  for (const n of fs.readdirSync(dir)) {
    const p = path.join(dir, n);
    let st; try { st = fs.statSync(p); } catch (e) { continue; }
    if (st.isDirectory()) walk(p, acc);
    else if (n.toLowerCase().endsWith('.md')) acc.push(p);
  }
  return acc;
}

const SEC = path.join(ROOT, '08-官方体系课程');
const files = walk(SEC, []);
console.log('扫描 markdown 文件: ' + files.length + '\n');

let refs = 0, ok = 0, miss = 0;
const missing = new Map();     // 缺失路径 -> 引用它的文件数
const byPrefix = new Map();    // 缺失路径的顶层目录 -> 数量

for (const f of files) {
  const rel = path.relative(ROOT, f).replace(/\\/g, '/');
  const baseDir = rel.split('/').slice(0, -1).join('/');
  let text; try { text = fs.readFileSync(f, 'utf8'); } catch (e) { continue; }
  let out; try { out = R.renderMarkdown(text, baseDir); } catch (e) { continue; }

  const srcs = [...out.html.matchAll(/<img[^>]*\ssrc="\/api\/raw\?path=([^"]+)"/g)]
                 .map(m => decodeURIComponent(m[1]));
  for (const s of srcs) {
    // 去掉 query（有些是 ?WT.mc_id=...）
    const clean = s.split('?')[0];
    refs++;
    const abs = path.join(ROOT, clean.replace(/\//g, '\\'));
    if (fs.existsSync(abs)) { ok++; continue; }
    miss++;
    missing.set(clean, (missing.get(clean) || 0) + 1);
    const seg = clean.split('/');
    // 缺失路径所属的仓库+顶层目录
    const key = seg.slice(0, 3).join('/');
    byPrefix.set(key, (byPrefix.get(key) || 0) + 1);
  }
}

console.log('='.repeat(66));
console.log('  图片引用总数 : ' + refs);
console.log('  存在         : ' + ok);
console.log('  缺失         : ' + miss + '  (唯一 ' + missing.size + ' 个)');
console.log('='.repeat(66));

console.log('\n缺失路径按目录聚合（这些目录需要补拉）:');
[...byPrefix.entries()].sort((a, b) => b[1] - a[1]).forEach(([k, v]) =>
  console.log('  ' + String(v).padStart(4) + '  ' + k));

console.log('\n缺失样例（前 15）:');
[...missing.keys()].slice(0, 15).forEach(k => console.log('  ' + k));

// 写出补拉清单供下一步使用
const outFile = 'C:\\StudyAI\\_webapp\\_build\\missing-paths.txt';
fs.writeFileSync(outFile, [...byPrefix.keys()].join('\n'), 'utf8');
console.log('\n补拉目录清单已写入: ' + outFile);
