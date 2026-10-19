/* =====================================================================
   render-core.js —— 把「动画网页」逐帧渲染成 mp4 的核心

   约定（页面侧）
     页面只需暴露两个东西：
       window.<durationExpr>   总时长（秒）
       window.<seekExpr>(t)    把页面渲染成第 t 秒的状态（确定性，不依赖 CSS 过渡）
     并提供一个 ?render=1 之类的模式，用来关掉开场遮罩、播放控制条、CSS 过渡。

   原理
     1. 起 headless Edge，开远程调试端口
     2. Node 内置 WebSocket 连 CDP（不需要 Playwright）
     3. 逐帧 evaluate(seekExpr(t)) → Page.captureScreenshot
     4. PNG 直接管道给 ffmpeg 的 stdin（不落盘）
   ===================================================================== */
'use strict';

const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');

const DEFAULTS = {
  edge: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  ffmpeg: 'C:\\tools\\ffmpeg\\ffmpeg.exe',
  fps: 30,
  width: 1920,
  height: 1080,
  durationExpr: 'window.__filmTotal',
  seekExpr: '__renderFrame',
  crf: 18,
  preset: 'medium',
  port: 9333
};

const sleep = ms => new Promise(r => setTimeout(r, ms));

function httpJSON(port, p) {
  return new Promise((resolve, reject) => {
    http.get({ host: '127.0.0.1', port, path: p }, res => {
      let b = '';
      res.on('data', d => (b += d));
      res.on('end', () => { try { resolve(JSON.parse(b)); } catch (e) { reject(e); } });
    }).on('error', reject);
  });
}

class CDP {
  constructor(wsUrl) { this.ws = new WebSocket(wsUrl); this.id = 0; this.waiting = new Map(); }
  ready() {
    return new Promise((res, rej) => {
      this.ws.addEventListener('open', () => res());
      this.ws.addEventListener('error', () => rej(new Error('WebSocket 连接失败')));
    });
  }
  bind() {
    this.ws.addEventListener('message', ev => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }
      if (msg.id && this.waiting.has(msg.id)) {
        const { res, rej } = this.waiting.get(msg.id);
        this.waiting.delete(msg.id);
        msg.error ? rej(new Error(msg.error.message)) : res(msg.result);
      }
    });
  }
  send(method, params) {
    const id = ++this.id;
    return new Promise((res, rej) => {
      this.waiting.set(id, { res, rej });
      this.ws.send(JSON.stringify({ id, method, params: params || {} }));
    });
  }
  close() { try { this.ws.close(); } catch (e) {} }
}

/* 探一下环境：返回各组件是否可用 */
function probeEnv(o) {
  o = Object.assign({}, DEFAULTS, o || {});
  const out = { edge: { path: o.edge, ok: fs.existsSync(o.edge) }, ffmpeg: { path: o.ffmpeg, ok: fs.existsSync(o.ffmpeg) } };
  try {
    const v = require('child_process').execFileSync(o.ffmpeg, ['-version'], { encoding: 'utf8', timeout: 10000 });
    out.ffmpeg.version = (v.split('\n')[0] || '').trim();
  } catch (e) { out.ffmpeg.version = null; }
  try {
    // Windows 上 msedge --version 输出本地化文案，直接取文件版本更可靠
    const ps = 'powershell -NoProfile -Command "(Get-Item \'' + o.edge.replace(/'/g, "''") +
               '\').VersionInfo.ProductVersion"';
    const v = require('child_process').execSync(ps, { encoding: 'utf8', timeout: 15000 });
    out.edge.version = (v || '').trim() || null;
  } catch (e) { out.edge.version = null; }
  return out;
}

/* 主函数 */
async function renderVideo(opts) {
  const o = Object.assign({}, DEFAULTS, opts || {});
  if (!o.url)  throw new Error('缺少 url');
  if (!o.out)  throw new Error('缺少 out');
  if (!fs.existsSync(o.edge))   throw new Error('找不到 Edge: ' + o.edge);
  if (!fs.existsSync(o.ffmpeg)) throw new Error('找不到 ffmpeg: ' + o.ffmpeg);

  const log = o.onProgress || (() => {});
  const t0 = Date.now();
  const userDir = path.join(os.tmpdir(), 'edge-render-' + Date.now());
  let edge = null, cdp = null;

  try {
    log({ stage: 'launch', message: '启动浏览器' });
    edge = spawn(o.edge, [
      '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
      '--hide-scrollbars', '--mute-audio', '--force-device-scale-factor=1',
      '--window-size=' + o.width + ',' + o.height,
      '--user-data-dir=' + userDir,
      '--remote-debugging-port=' + o.port,
      'about:blank'
    ], { stdio: 'ignore' });

    let list = null;
    for (let i = 0; i < 80; i++) {
      try { list = await httpJSON(o.port, '/json/list'); if (list && list.length) break; } catch (e) {}
      await sleep(250);
    }
    if (!list) throw new Error('浏览器调试端口没起来（端口 ' + o.port + ' 可能被占用）');

    const target = list.find(t => t.type === 'page') || list[0];
    cdp = new CDP(target.webSocketDebuggerUrl);
    cdp.bind();
    await cdp.ready();
    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');

    log({ stage: 'navigate', message: '打开页面 ' + o.url });
    await cdp.send('Page.navigate', { url: o.url });
    await sleep(o.settleMs || 3500);

    const rr = await cdp.send('Runtime.evaluate', {
      expression: o.durationExpr, returnByValue: true
    });
    const total = Number(rr.result.value);
    if (!total || !isFinite(total)) {
      throw new Error('页面没有暴露总时长（表达式：' + o.durationExpr + '）');
    }

    const frames = Math.round(total * o.fps);
    log({ stage: 'start', total, fps: o.fps, frames, width: o.width, height: o.height });

    fs.mkdirSync(path.dirname(o.out), { recursive: true });
    const ff = spawn(o.ffmpeg, [
      '-y',
      '-f', 'image2pipe', '-framerate', String(o.fps), '-i', '-',
      '-c:v', 'libx264', '-preset', o.preset, '-crf', String(o.crf),
      '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
      '-vf', 'scale=' + o.width + ':' + o.height + ':flags=lanczos',
      o.out
    ], { stdio: ['pipe', 'ignore', 'pipe'] });

    const ffErr = [];
    ff.stderr.on('data', d => { ffErr.push(d.toString()); if (ffErr.length > 200) ffErr.shift(); });
    let ffDone = new Promise(res => ff.on('close', res));

    const writeAsync = buf => new Promise(res => {
      if (!ff.stdin.writable) return res();
      ff.stdin.write(buf) ? res() : ff.stdin.once('drain', res);
    });

    const started = Date.now();
    for (let n = 0; n < frames; n++) {
      if (typeof o.shouldStop === 'function' && o.shouldStop()) {
        throw new Error('已取消');
      }
      const t = n / o.fps;
      await cdp.send('Runtime.evaluate', { expression: o.seekExpr + '(' + t.toFixed(5) + ')' });
      const shot = await cdp.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
      await writeAsync(Buffer.from(shot.data, 'base64'));

      if (n % 5 === 0 || n === frames - 1) {
        const el = (Date.now() - started) / 1000;
        log({
          stage: 'render',
          frame: n + 1, frames,
          percent: +((n + 1) / frames * 100).toFixed(1),
          elapsedSec: +el.toFixed(0),
          etaSec: n > 0 ? +((el / (n + 1)) * (frames - n - 1)).toFixed(0) : null
        });
      }
    }

    ff.stdin.end();
    log({ stage: 'encode-wait', message: '等待 ffmpeg 收尾' });
    await ffDone;

    if (!fs.existsSync(o.out)) {
      throw new Error('编码失败：\n' + ffErr.join('').slice(-1500));
    }
    const mb = fs.statSync(o.out).size / 1024 / 1024;
    const result = {
      ok: true,
      out: o.out,
      bytes: fs.statSync(o.out).size,
      mb: +mb.toFixed(2),
      durationSec: total,
      fps: o.fps,
      width: o.width,
      height: o.height,
      frames,
      elapsedSec: +((Date.now() - t0) / 1000).toFixed(0)
    };
    log({ stage: 'done', result });
    return result;
  } finally {
    if (cdp) cdp.close();
    if (edge) { try { edge.kill(); } catch (e) {} }
    await sleep(500);
    try { fs.rmSync(userDir, { recursive: true, force: true }); } catch (e) {}
  }
}

module.exports = { renderVideo, probeEnv, DEFAULTS };
