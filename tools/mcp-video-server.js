#!/usr/bin/env node
/* =====================================================================
   mcp-video-server.js —— 动画网页 → 视频 的 MCP 服务（stdio）

   工具
     check_video_env     检查 Edge / ffmpeg
     render_animation    提交渲染任务
                           · wait=true  阻塞到出片（适合小规格，≤720p/≤15fps）
                           · 默认异步   立即返回 taskId，用 get_render_status 轮询
     get_render_status   查任务进度 / 结果
     cancel_render       取消任务（已开始编码的部分会丢弃）
     list_render_tasks   列出本会话所有任务

   为什么要异步
     1080p/30fps 渲染 65 秒动画约需 3 分钟，超过 MCP 调用的响应时限。
     异步模式先返回 taskId，避免调用方超时报错。

   页面约定
     window.<durationExpr>   总时长（秒）
     window.<seekExpr>(t)    渲染第 t 秒的状态
     以及一个关闭遮罩/控制条/CSS 过渡的 URL 参数（通常 ?render=1）

   注册（$DSH_HOME/cordis.patch.yml）
     - insert:
         - id: video-export-mcp
           name: '@deepseek-ai/dsh-mcp-client'
           config:
             serverName: video
             transport: stdio
             command: 'C:\Program Files\nodejs\node.exe'
             args: [ 'C:/StudyAI/tools/mcp-video-server.js' ]
   ===================================================================== */
'use strict';

const readline = require('readline');
const fs = require('fs');
const { renderVideo, probeEnv } = require('./render-core');

const PROTOCOL = '2024-11-05';
const SERVER = { name: 'video-export', version: '1.1.0' };

/* ---------------- 任务表 ---------------- */
const TASKS = new Map();
let seq = 0;

function newTask(args) {
  const id = 'r' + (++seq).toString().padStart(3, '0');
  const task = {
    id,
    status: 'running',          // running | done | failed | cancelled
    createdAt: new Date().toISOString(),
    startedAt: Date.now(),
    args,
    progress: { stage: 'queued', percent: 0 },
    result: null,
    error: null,
    cancelRequested: false
  };
  TASKS.set(id, task);
  return task;
}

function publicView(t) {
  const ageSec = Math.round((Date.now() - t.startedAt) / 1000);
  return {
    taskId: t.id,
    status: t.status,
    elapsedSec: ageSec,
    progress: t.progress,
    out: t.args && t.args.out,
    result: t.result,
    error: t.error,
    cancelRequested: t.cancelRequested
  };
}

/* ---------------- 工具定义 ---------------- */
const TOOLS = [
  {
    name: 'check_video_env',
    description:
      '检查视频导出环境：Edge 浏览器、ffmpeg（需 libx264）是否可用，返回版本号。' +
      '导出前先调这个，缺东西会直接告诉你缺哪个路径。',
    inputSchema: { type: 'object', properties: {}, additionalProperties: false }
  },
  {
    name: 'render_animation',
    description:
      '把「可定位动画网页」逐帧渲染成 mp4。不是录屏 —— 按时间精确计算每一帧再编码，' +
      '所以帧率恒定、时间无漂移、无鼠标光标、可任意改分辨率。\n\n' +
      '默认异步：立即返回 taskId，之后用 get_render_status 轮询。' +
      '1080p/30fps 渲染 60 秒动画约需 3 分钟，异步可避免调用超时。\n' +
      '小规格（≤720p 且 ≤15fps）可以传 wait=true 直接阻塞拿结果。\n\n' +
      '页面需暴露 window.<durationExpr>（总时长秒）与 window.<seekExpr>(t)，' +
      '并有一个关闭遮罩/控制条/CSS 过渡的 URL 参数（通常 ?render=1）。',
    inputSchema: {
      type: 'object',
      properties: {
        url:          { type: 'string', description: '动画页 URL，需带 render 模式参数，例如 http://127.0.0.1:8777/film?render=1' },
        out:          { type: 'string', description: '输出 mp4 的绝对路径' },
        fps:          { type: 'number', description: '帧率，默认 30' },
        width:        { type: 'number', description: '宽度，默认 1920' },
        height:       { type: 'number', description: '高度，默认 1080' },
        durationExpr: { type: 'string', description: '取总时长的 JS 表达式，默认 window.__filmTotal' },
        seekExpr:     { type: 'string', description: '定位到某一时刻的全局函数名，默认 __renderFrame' },
        crf:          { type: 'number', description: 'x264 质量，默认 18（越小越清晰）' },
        preset:       { type: 'string', description: 'x264 preset，默认 medium' },
        settleMs:     { type: 'number', description: '页面加载后等待毫秒，默认 3500' },
        wait:         { type: 'boolean', description: 'true 则阻塞到出片；默认 false（异步，返回 taskId）' }
      },
      required: ['url', 'out'],
      additionalProperties: false
    }
  },
  {
    name: 'get_render_status',
    description: '查询渲染任务状态。status 为 running / done / failed / cancelled。done 时 result 里含文件路径、大小、时长、帧数。',
    inputSchema: {
      type: 'object',
      properties: {
        taskId: { type: 'string', description: 'render_animation 返回的 taskId；留空则返回全部任务概览' }
      },
      additionalProperties: false
    }
  },
  {
    name: 'cancel_render',
    description: '取消一个正在渲染的任务。已写入的部分文件会被删除。',
    inputSchema: {
      type: 'object',
      properties: { taskId: { type: 'string', description: '要取消的 taskId' } },
      required: ['taskId'],
      additionalProperties: false
    }
  },
  {
    name: 'list_render_tasks',
    description: '列出本会话提交过的所有渲染任务及其状态。',
    inputSchema: { type: 'object', properties: {}, additionalProperties: false }
  }
];

/* ---------------- 启动一个渲染任务 ---------------- */
function startRender(args) {
  const task = newTask(args);

  renderVideo(Object.assign({}, args, {
    onProgress: ev => {
      task.progress = ev.stage === 'render'
        ? { stage: 'render', percent: ev.percent, frame: ev.frame, frames: ev.frames, etaSec: ev.etaSec }
        : { stage: ev.stage, message: ev.message || null };
      if (ev.stage === 'start') {
        task.progress.total = ev.total;
        task.progress.frames = ev.frames;
        task.progress.width = ev.width;
        task.progress.height = ev.height;
        task.progress.fps = ev.fps;
      }
    },
    shouldStop: () => task.cancelRequested
  })).then(r => {
    task.status = 'done';
    task.result = r;
    task.progress = { stage: 'done', percent: 100 };
  }).catch(e => {
    if (task.cancelRequested) {
      task.status = 'cancelled';
      task.error = '已取消';
    } else {
      task.status = 'failed';
      task.error = e.message;
    }
    /* 失败/取消时清掉半成品，避免留下坏文件 */
    try {
      if (args.out && fs.existsSync(args.out) && task.status !== 'done') fs.unlinkSync(args.out);
    } catch (err) {}
  });

  return task;
}

/* ---------------- 工具实现 ---------------- */
async function callTool(name, args) {
  if (name === 'check_video_env') {
    const env = probeEnv(args || {});
    const ok = env.edge.ok && env.ffmpeg.ok;
    return {
      content: [{
        type: 'text',
        text: JSON.stringify({
          ok,
          edge: env.edge,
          ffmpeg: env.ffmpeg,
          hint: ok
            ? '环境就绪，可以直接调 render_animation'
            : '缺少组件：把 edge/ffmpeg 路径补上，或在参数里传 edge/ffmpeg 覆盖默认值'
        }, null, 2)
      }]
    };
  }

  if (name === 'render_animation') {
    if (!args || !args.url || !args.out) throw new Error('必须提供 url 和 out');

    /* 阻塞模式：小规格才建议 */
    if (args.wait === true) {
      const r = await renderVideo(args);
      return { content: [{ type: 'text', text: JSON.stringify(r, null, 2) }] };
    }

    /* 默认异步 */
    const t = startRender(args);
    return {
      content: [{
        type: 'text',
        text: JSON.stringify({
          taskId: t.id,
          status: 'running',
          out: args.out,
          hint: '已开始渲染。用 get_render_status 查进度（taskId=' + t.id + '）。' +
                '1080p/30fps 约需 2~4 分钟。'
        }, null, 2)
      }]
    };
  }

  if (name === 'get_render_status') {
    const id = args && args.taskId;
    if (id) {
      const t = TASKS.get(id);
      if (!t) throw new Error('没有这个任务: ' + id);
      return { content: [{ type: 'text', text: JSON.stringify(publicView(t), null, 2) }] };
    }
    const all = [...TASKS.values()].map(publicView);
    return {
      content: [{
        type: 'text',
        text: JSON.stringify({ count: all.length, tasks: all }, null, 2)
      }]
    };
  }

  if (name === 'cancel_render') {
    const t = TASKS.get(args && args.taskId);
    if (!t) throw new Error('没有这个任务: ' + (args && args.taskId));
    if (t.status !== 'running') {
      return { content: [{ type: 'text', text: JSON.stringify({ taskId: t.id, status: t.status, message: '任务已结束，无需取消' }) }] };
    }
    t.cancelRequested = true;
    return {
      content: [{
        type: 'text',
        text: JSON.stringify({ taskId: t.id, status: 'cancelling', message: '已请求取消，当前帧处理完即停止' })
      }]
    };
  }

  if (name === 'list_render_tasks') {
    const all = [...TASKS.values()].map(t => ({
      taskId: t.id, status: t.status, out: t.args && t.args.out,
      percent: (t.progress && t.progress.percent) || 0
    }));
    return { content: [{ type: 'text', text: JSON.stringify({ count: all.length, tasks: all }, null, 2) }] };
  }

  throw new Error('未知工具: ' + name);
}

/* ---------------- JSON-RPC over stdio ---------------- */
const send = msg => process.stdout.write(JSON.stringify(msg) + '\n');
const reply = (id, result) => send({ jsonrpc: '2.0', id, result });
const replyErr = (id, code, message) => send({ jsonrpc: '2.0', id, error: { code, message } });

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });

rl.on('line', async line => {
  line = line.trim();
  if (!line) return;
  let msg;
  try { msg = JSON.parse(line); } catch (e) { return; }

  const { id, method, params } = msg;

  try {
    switch (method) {
      case 'initialize':
        return reply(id, { protocolVersion: PROTOCOL, capabilities: { tools: {} }, serverInfo: SERVER });
      case 'notifications/initialized':
      case 'initialized':
        return;
      case 'ping':
        return reply(id, {});
      case 'tools/list':
        return reply(id, { tools: TOOLS });
      case 'tools/call': {
        const name = params && params.name;
        const args = (params && params.arguments) || {};
        try {
          return reply(id, await callTool(name, args));
        } catch (e) {
          return reply(id, { content: [{ type: 'text', text: '❌ ' + e.message }], isError: true });
        }
      }
      case 'resources/list': return reply(id, { resources: [] });
      case 'prompts/list':   return reply(id, { prompts: [] });
      default:
        if (id != null) replyErr(id, -32601, 'Method not found: ' + method);
        return;
    }
  } catch (e) {
    if (id != null) replyErr(id, -32603, e.message);
  }
});

rl.on('close', () => process.exit(0));
process.stderr.write('[video-export] MCP server ready (v1.1.0, async render)\n');
