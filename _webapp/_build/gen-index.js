/* 从中文课程 README 中提取每课真实标题，生成索引 Markdown */
const fs = require('fs');
const path = require('path');

const SEC = 'C:\\StudyAI\\08-官方体系课程';

function h1(file) {
  try {
    const t = fs.readFileSync(file, 'utf8');
    const m = t.match(/^#\s+(.+)$/m);
    if (!m) return null;
    return m[1].replace(/[#*`]/g, '').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').trim();
  } catch (e) { return null; }
}

function sizeMB(p) {
  let s = 0;
  for (const n of fs.readdirSync(p)) {
    const f = path.join(p, n); const st = fs.statSync(f);
    if (st.isDirectory()) s += sizeMB(f); else s += st.size;
  }
  return s / 1048576;
}

// ---- 微软两套课程 ----
const MS = [
  { dir: 'generative-ai-for-beginners', org: '微软', total: 21,
    cn: '面向初学者的生成式 AI', note: '从生成式 AI 概念到 RAG、微调、Agent 的完整 21 课' },
  { dir: 'ai-agents-for-beginners', org: '微软', total: 18,
    cn: '面向初学者的 AI 代理', note: 'Agent 开发 18 课：设计模式、工具调用、多智能体、MCP、生产化' }
];

const out = [];
out.push('# 08 · 官方体系课程');
out.push('');
out.push('> 微软官方 × Hugging Face 官方出品的**成体系课程**，与 `01`~`07` 的专题资料互补。');
out.push('> 微软两套课程已下载**简体中文版**（仅中文正文 + 中文配图）。');
out.push('');
out.push('---');
out.push('');

for (const c of MS) {
  const base = path.join(SEC, c.dir, 'translations', 'zh-CN');
  if (!fs.existsSync(base)) { out.push('（缺失：' + c.dir + '）'); continue; }
  const lessons = fs.readdirSync(base)
    .filter(n => fs.statSync(path.join(base, n)).isDirectory() && /^\d/.test(n))
    .sort();
  out.push(`## ${c.cn} · ${c.dir}`);
  out.push('');
  out.push(`${c.org}官方课程，共 ${c.total} 课。${c.note}`);
  out.push('');
  out.push(`📖 **入口：[打开课程索引](translations/zh-CN/README.md)**　（学习台里点此文件即可）`);
  out.push('');
  out.push('| # | 课程 | 目录 |');
  out.push('|---|---|---|');
  for (const l of lessons) {
    const t = h1(path.join(base, l, 'README.md')) || l.replace(/^\d+-/, '').replace(/-/g, ' ');
    const no = (l.match(/^(\d+)/) || [, ''])[1];
    out.push(`| ${no} | ${t} | \`${l}\` |`);
  }
  out.push('');
  out.push('---');
  out.push('');
}

// ---- HF 两套 ----
out.push('## Hugging Face 官方课程 · huggingface-course');
out.push('');
out.push('HF 官方维护，覆盖 Transformer 架构、模型微调、数据集处理，代码与官方库同步更新。');
out.push('');
const HF = path.join(SEC, 'huggingface-course', 'chapters');
if (fs.existsSync(HF)) {
  const langs = fs.readdirSync(HF).filter(n => fs.statSync(path.join(HF, n)).isDirectory());
  out.push('| 语言 | 章节数 | 目录 |');
  out.push('|---|---|---|');
  for (const lg of langs) {
    const n = fs.readdirSync(path.join(HF, lg)).filter(f => f.endsWith('.md')).length;
    out.push(`| ${lg} | ${n} | \`chapters/${lg}/\` |`);
  }
  out.push('');
  out.push('> 提示：只有 `en` 是完整官方内容，其余语言为社区翻译，可能滞后。');
}
out.push('');
out.push('---');
out.push('');

out.push('## 大模型路线图 · llm-course');
out.push('');
out.push('Hugging Face 工程师 Maxime Labonne 创建，GitHub 83k+ Star。');
out.push('提供**双路径**（「科学家」与「工程师」），大量可直接在 Colab 运行的 Notebook。');
out.push('');
out.push('📖 **入口：[打开路线图](llm-course/README.md)**');
out.push('');
out.push('> 注意：此仓库正文主要是路线图与外链，实际 Notebook 托管在 Hugging Face Hub 上，需要联网打开。');
out.push('');
out.push('---');
out.push('');
out.push(`*本版块共 ${sizeMB(SEC).toFixed(2)} MB*`);
out.push('');

const target = path.join(SEC, 'README.md');
fs.writeFileSync(target, out.join('\n'), 'utf8');
console.log('已生成: ' + target + '  (' + out.join('\n').length + ' 字符)');

// 给两个微软课程各加一个入口提示文件
for (const c of MS) {
  const p = path.join(SEC, c.dir, 'README.md');
  const body = [
    `# ${c.cn}`,
    '',
    '> 本目录是 **简体中文版**，只包含中文课程正文与中文配图。',
    '',
    '## 从这里开始',
    '',
    '[**▶ 打开中文课程索引**](translations/zh-CN/README.md)',
    '',
    '## 目录说明',
    '',
    '| 路径 | 内容 |',
    '|---|---|',
    '| `translations/zh-CN/` | 中文课程正文（每课一个子目录，各有 README.md） |',
    '| `translated_images/zh-CN/` | 中文配图（课程正文以相对路径引用，**请勿移动**） |',
    '| `images/` | 少量共享配图 |',
    '',
    '> ⚠️ `translations/` 与 `translated_images/` 的相对层级不能改动，否则课程内图片会全部失效。',
    ''
  ].join('\n');
  fs.writeFileSync(p, body, 'utf8');
  console.log('已生成入口: ' + p);
}
