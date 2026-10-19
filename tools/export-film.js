#!/usr/bin/env node
/* =====================================================================
   export-film.js —— CLI 包装（核心逻辑在 render-core.js）

   用法
     node tools/export-film.js [输出文件] [--fps 30] [--w 1920] [--h 1080]
     node tools/export-film.js out.mp4 --fps 60 --w 3840 --h 2160

   默认导出 http://127.0.0.1:8777/film?render=1
   ===================================================================== */
'use strict';

const { renderVideo } = require('./render-core');

const argv = process.argv.slice(2);
const opt = (name, def) => {
  const i = argv.indexOf('--' + name);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : def;
};

const OUT = (argv[0] && !argv[0].startsWith('--'))
  ? argv[0]
  : 'C:\\StudyAI\\docs\\大肥鱼阅读器-介绍片.mp4';

renderVideo({
  url: opt('url', 'http://127.0.0.1:8777/film?render=1'),
  out: OUT,
  fps: parseInt(opt('fps', '30'), 10),
  width: parseInt(opt('w', '1920'), 10),
  height: parseInt(opt('h', '1080'), 10),
  crf: parseInt(opt('crf', '18'), 10),
  onProgress: ev => {
    if (ev.stage === 'render') {
      process.stdout.write('\r   ' + String(ev.percent).padStart(5) + '%   ' +
        ev.frame + '/' + ev.frames + ' 帧   已用 ' + ev.elapsedSec + 's   剩约 ' +
        (ev.etaSec == null ? '?' : ev.etaSec) + 's   ');
    } else if (ev.stage === 'start') {
      console.log('  总时长 ' + ev.total.toFixed(1) + ' 秒 · ' + ev.fps + ' fps · ' +
        ev.frames + ' 帧 · ' + ev.width + '×' + ev.height);
    } else if (ev.stage === 'launch' || ev.stage === 'navigate') {
      console.log('▶ ' + ev.message + ' …');
    } else if (ev.stage === 'done') {
      process.stdout.write('\n');
    }
  }
}).then(r => {
  console.log('\n✅ 完成');
  console.log('  文件 : ' + r.out);
  console.log('  大小 : ' + r.mb + ' MB');
  console.log('  规格 : ' + r.width + '×' + r.height + ' / ' + r.fps + ' fps / ' + r.durationSec.toFixed(1) + ' 秒');
  console.log('  耗时 : ' + r.elapsedSec + ' 秒');
}).catch(e => {
  console.error('\n❌ ' + e.message);
  process.exit(1);
});
