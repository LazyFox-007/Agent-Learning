/* =====================================================================
   生成 roadmap.js —— 面向「AI Agent 全栈课程」
   数据源：01-AI-Agent全栈课程/index.html（7 层 / 37 章的真实结构）
   ===================================================================== */
const fs = require('fs');
const path = require('path');

const ROOT = 'C:\\StudyAI';
const DIR  = '01-AI-Agent全栈课程';
const ABS  = path.join(ROOT, DIR);
const rel  = p => path.relative(ROOT, p).replace(/\\/g, '/');
const strip = s => String(s).replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();

const html = fs.readFileSync(path.join(ABS, 'index.html'), 'utf8');

/* ---------- 解析 7 层 / 37 章 ---------- */
const layers = [];
const layerRe = /<div class="layer">\s*<div class="layer-title">(.*?)<\/div>\s*<div class="layer-bg">([\s\S]*?)<\/table>/g;
let L;
while ((L = layerRe.exec(html)) !== null) {
  const name = strip(L[1]);
  const items = [];
  const rowRe = /<span class="ch-num">(.*?)<\/span>\s*<a href="([^"]+)">(.*?)<\/a>\s*<span class="ch-tech">(.*?)<\/span>/g;
  let R2;
  while ((R2 = rowRe.exec(L[2])) !== null) {
    const no = strip(R2[1]);
    const href = R2[2].trim();
    const title = strip(R2[3]);
    const tech = strip(R2[4]);
    const pageAbs = path.join(ABS, href.replace(/\//g, '\\'));

    // 同名 .py
    const chapDir = path.dirname(pageAbs);
    let pyPath = null;
    try {
      const py = fs.readdirSync(chapDir).find(f => f.endsWith('.py'));
      if (py) pyPath = rel(path.join(chapDir, py));
    } catch (e) {}

    items.push({ no, title, tech, path: rel(pageAbs), py: pyPath });
  }
  const range = (name.match(/\(([^)]+)\)/) || [, ''])[1];
  layers.push({
    no: '第' + (layers.length + 1) + '层',
    title: name.replace(/^第\d+层：/, '').replace(/\s*\([^)]*\)\s*$/, ''),
    time: range || '',
    key: layers.length === 2,          // 第3层「深度技术剖析」是关键分水岭
    badge: layers.length === 2 ? '核心分水岭' : undefined,
    desc: '',                          // 解析完再统一填（见下方 LAYER_DESC_get）
    items
  });
}

/* ---------- 组装 ---------- */
const totalCh = layers.reduce((n, l) => n + l.items.length, 0);

const DATA = {
  courses: [{
    org: 'callous-0923', badge: '简体中文', star: true,
    name: 'AI Agent 全栈课程',
    repo: 'agent-study',
    lessons: totalCh,
    level: '入门 → 专家',
    desc: '从 ReAct 循环裸写开始，经 Claude Code 架构逆向、MCP / A2A 协议、RAG 深度、'
        + 'Agentic Workflow、可观测性，直到纵深安全 —— 37 章全部配可运行 Python 源码。',
    note: 'MIT License · 已本地化（1,661 处链接改写为相对路径，可完全离线阅读）',
    entry: DIR + '/index.html',
    dir: DIR,
    repoUrl: 'https://github.com/callous-0923/agent-study'
  }],
  stages: layers,
  extra: null,
  agentPath: null,
  env: {
    title: '运行环境',
    sub: '课程自带 requirements.txt。Ch8 之后大多只用标准库，不装依赖也能读代码。',
    code: [
      'cd C:\\StudyAI\\01-AI-Agent全栈课程',
      '',
      '# 1) 安装课程依赖（Ch1-5 需要 openai / langchain / langgraph）',
      'python -m pip install -r requirements.txt',
      '',
      '# 2) 配置 API Key —— 在课程根目录新建 .env',
      '#    OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx',
      '#    OPENAI_BASE_URL=https://api.deepseek.com/v1   # 或用国产模型',
      '#    LLM_MODEL=deepseek-chat',
      '',
      '# 3) 国内 pip 加速（可选）',
      'pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple',
      '',
      '# 4) 验证 Python 版本（课程要求 3.10+）',
      'python --version'
    ].join('\n'),
    note: '课程 <code>Ch0</code> 里有完整的 API Key 配置指南与一键环境检查脚本。'
        + '国产模型（DeepSeek / 通义千问）改 <code>OPENAI_BASE_URL</code> 即可直接跑。'
  },
  paths: {
    title: '按目标选路径',
    sub: '来自课程 Ch0 的学习建议',
    items: [
      { t: '新手入门', d: '按 Ch0 → Ch36 顺序，每章 1–2 小时', chapters: '全部 37 章' },
      { t: '有基础', d: '直接跳 Ch8 开始深度技术', chapters: 'Ch8–36' },
      { t: '面试突击', d: '高频考点 8 章', chapters: 'Ch7 · Ch8 · Ch9 · Ch10 · Ch11 · Ch15 · Ch18 · Ch19' },
      { t: '构建产品', d: '服务化 + 持久化 + 可观测 + 路由 + 缓存', chapters: 'Ch13 · Ch14 · Ch24 · Ch26 · Ch28' },
      { t: '降本增效', d: '路由与缓存组合拳', chapters: 'Ch26 · Ch28 · Ch33' }
    ]
  },
  onlineBooks: [
    { t: '课程原仓库（GitHub）', u: 'https://github.com/callous-0923/agent-study' },
    { t: '课程在线版（作者站点）', u: 'https://callous-0923.github.io/agent-study/index.html' }
  ]
};

/* 各层导语 + 过关标准 */
const LAYER_DESC = [
  '建立直觉：Agent 是什么、和普通 LLM 差在哪、核心组件有哪些。',
  '上手工程：主流框架、多智能体协作、怎么评测、面试怎么答。',
  '啃源码级细节：Claude Code 架构、RAG 生产级方案、MCP / Tool Calling 协议底层。',
  '补齐工程化：FastAPI 服务化、SQLite 持久化、A2A 协议、记忆系统、Computer Use、安全护栏。',
  '架构进阶：Agentic Workflow 模式、上下文工程、流式架构、DSPy 优化、代码 Agent 横评、可观测性。',
  '补基础短板：向量库选型、模型路由、Prompt 工程、语义缓存。',
  '专家级话题：多模态、可靠性工程、评测基准、自改进、Prompt Cache、微调、数据飞轮、纵深安全。'
];

const LAYER_PASS = [
  '能说清 Agent 与普通 LLM 的本质区别；不看示例能手写一个最小 ReAct 循环。',
  '能用 LangGraph 搭一个带状态流转的 Agent；能设计出 Writer + Reviewer 这类多智能体协作。',
  '能讲清 Claude Code 主循环为什么这么设计；说得清 MCP 解决了什么协议层问题。',
  '能把 Agent 包装成 FastAPI 服务，会话状态落到 SQLite，并加上基本的安全护栏。',
  '能独立设计一条 Agentic Workflow；会做上下文压缩、流式输出与基础可观测埋点。',
  '能根据场景选向量库；会按成本/质量做模型路由；能上语义缓存把 token 成本压下来。',
  '能设计 Agent 的可靠性与纵深安全方案；看得懂主流评测基准，知道各自测的是什么。'
];

function LAYER_DESC_get(i) {
  return LAYER_DESC[i] || '';
}

// 给每层填 desc / pass（放在解析后，避免函数未定义）
layers.forEach((l, i) => {
  l.desc = LAYER_DESC_get(i);
  l.pass = LAYER_PASS[i] || '';
});

const header = [
  '/* =====================================================================',
  '   StudyAI 学习路线数据',
  '   由 _webapp/_build/gen-roadmap.js 自动生成，请勿手改',
  '   生成时间: ' + new Date().toISOString().replace('T', ' ').slice(0, 19),
  '   内容: AI Agent 全栈课程 · ' + layers.length + ' 层 / ' + totalCh + ' 章',
  '   ===================================================================== */',
  'window.ROADMAP = ' + JSON.stringify(DATA, null, 2) + ';',
  ''
].join('\n');

fs.writeFileSync(path.join(ROOT, '_webapp', 'static', 'roadmap.js'), header, 'utf8');

console.log('已生成 roadmap.js  (' + (header.length / 1024).toFixed(1) + ' KB)');
console.log('  课程: ' + DATA.courses[0].name + '  ' + totalCh + ' 章');
console.log('');
layers.forEach(l => {
  console.log('  ' + l.no + ' ' + l.title.padEnd(16) + ' [' + String(l.time).padEnd(7) + ']  ' + l.items.length + ' 章');
});
console.log('');
console.log('  章节样例:');
const s = layers[0].items[0];
console.log('    ' + s.no + '  ' + s.title);
console.log('        html: ' + s.path);
console.log('        py  : ' + s.py);
