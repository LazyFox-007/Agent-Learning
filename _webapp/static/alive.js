/* =====================================================================
   存活心跳

   作用：告诉服务端「还有页面开着」。页面全关掉之后服务端会自动退出，
   不会留一个 python 进程在后台吃内存。

   工作方式
     · 页面打开时立刻注册一个 sid（存在 sessionStorage，同标签页复用）
     · 每 15 秒打一次心跳
     · 关闭 / 刷新 / 切到后台隐藏时，用 sendBeacon 报 bye
       —— sendBeacon 在页面卸载时也能可靠发出，普通 fetch 会被掐断

   服务端没开自动退出时，这些请求什么副作用都没有。
   ===================================================================== */
(function () {
  'use strict';

  var KEY = 'studyai.sid';
  var sid;

  try {
    sid = sessionStorage.getItem(KEY);
    if (!sid) {
      sid = Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem(KEY, sid);
    }
  } catch (e) {
    // 隐私模式下 sessionStorage 可能抛异常，退化成一次性 id
    sid = Math.random().toString(36).slice(2) + Date.now().toString(36);
  }

  var ALIVE_URL = '/api/heartbeat?sid=' + encodeURIComponent(sid);
  var BYE_URL = '/api/bye?sid=' + encodeURIComponent(sid);
  var timer = null;

  function beat() {
    fetch(ALIVE_URL, { cache: 'no-store', keepalive: true }).catch(function () {});
  }

  function bye() {
    if (navigator.sendBeacon) {
      try { navigator.sendBeacon(BYE_URL); return; } catch (e) {}
    }
    fetch(BYE_URL, { cache: 'no-store', keepalive: true }).catch(function () {});
  }

  function start() {
    beat();
    if (timer) clearInterval(timer);
    timer = setInterval(beat, 15000);
  }

  function stop() {
    if (timer) { clearInterval(timer); timer = null; }
  }

  // 页面隐藏（切标签页 / 最小化）时不停心跳 —— 用户还会回来。
  // 只有真正卸载时才报 bye。
  window.addEventListener('pagehide', bye);
  window.addEventListener('beforeunload', bye);

  // 从往返缓存恢复（浏览器后退）时重新注册
  window.addEventListener('pageshow', function (ev) {
    if (ev.persisted) start();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
