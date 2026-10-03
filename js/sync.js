/* ============ 同舟共济 · 登录守卫与学习数据同步 ============
   为什么需要：
   1. 学习端要密码才能进（密码校验只能在服务端做，前端 JS 是公开的）
   2. 管理端要能看到她的学习情况，数据就必须从她的浏览器同步到服务器

   设计要点：
   - 登录态用 HttpOnly Cookie，JS 读不到，也偷不走
   - 同步只上传统计数据，不上传题目与答案，也不上传 AI 的 Key
   - 服务端不可用时静默降级：本地照样能用，只是后台看不到
*/
(function () {
  'use strict';

  const API = {
    me: 'api/me',
    progress: 'api/progress',
    message: 'api/message',
  };

  let authed = false;
  let lastPush = 0;
  let pushing = false;

  /* ---------- 1. 登录守卫 ---------- */
  async function guard() {
    try {
      const r = await fetch(API.me, { credentials: 'same-origin' });
      if (r.status === 401) { location.replace('login.html'); return false; }
      if (!r.ok) return false;           // 服务端异常时放行，保证本地可用
      const d = await r.json();
      if (d.role === 'admin') { location.replace('admin.html'); return false; }
      authed = true;
      return true;
    } catch (_) {
      // 纯静态托管（没有后端）时不做拦截，保持离线可用
      return false;
    }
  }

  /* ---------- 2. 学习数据同步 ---------- */
  function snapshot() {
    const s = window.getStore ? window.getStore() : null;
    if (!s) return null;
    const byMod = {};
    for (const [m, v] of Object.entries(s.stats.byMod || {})) {
      byMod[m] = { answered: Number(v.answered) || 0, correct: Number(v.correct) || 0 };
    }
    return {
      answered: Number(s.stats.answered) || 0,
      correct: Number(s.stats.correct) || 0,
      byMod,
      daily: (s.stats.daily || []).slice(-60),
      streak: window.getStreak ? window.getStreak() : 0,
      wrongCount: Object.keys(s.wrongs || {}).length,
      essayCount: (s.essays || []).length,
      plan: s.plan || {},
      // 只传统计，不传题目、答案与 AI 配置
    };
  }

  async function push(force) {
    if (!authed || pushing) return;
    const now = Date.now();
    if (!force && now - lastPush < 60000) return;   // 心跳最少间隔 1 分钟
    const data = snapshot();
    if (!data) return;
    pushing = true;
    try {
      const r = await fetch(API.progress, {
        method: 'PUT',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (r.ok) lastPush = now;
    } catch (_) { /* 离线时静默跳过 */ }
    pushing = false;
  }

  /* ---------- 3. 她读得到留言（可以有多条） ---------- */
  async function showMessage() {
    if (!authed) return;
    try {
      const r = await fetch(API.message, { credentials: 'same-origin' });
      if (!r.ok) return;
      const d = await r.json();
      const list = (d.messages || []).filter(m => m && m.text);
      if (!list.length) return;
      const host = document.querySelector('#view');
      if (!host) return;
      const old = host.querySelector('.love-note');
      if (old) old.remove();
      const el = document.createElement('div');
      el.className = 'card love-note';
      el.innerHTML = '<h3><span class="dot"></span>他留给你的话</h3>';
      // 每条一行；纯文本插入，不用 innerHTML
      list.forEach(m => {
        const p = document.createElement('p');
        p.className = 'muted';
        p.style.cssText = 'font-size:15px;line-height:1.8;margin:0 0 6px';
        p.textContent = m.text;
        el.appendChild(p);
      });
      host.appendChild(el);
    } catch (_) {}
  }

  /* ---------- 4. 启动 ---------- */
  (async function start() {
    const ok = await guard();
    if (!ok) return;

    // 页面切到后台时推一次，保证「最后一次活跃时间」准确
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') push(true);
    });
    window.addEventListener('pagehide', () => { push(true); });

    // 答完题、交卷后立刻同步（不用等心跳）
    document.addEventListener('sat:answered', () => push(true));
    document.addEventListener('sat:bank-loaded', () => { push(true); setTimeout(showMessage, 400); });

    // 启动时探一次服务端 AI 配置：管理员在后台配好后，她的端就能直接用
    if (window.AI && window.AI.readyAsync) {
      window.AI.readyAsync().then(() => {
        document.dispatchEvent(new CustomEvent('sat:ai-ready'));
      }).catch(() => {});
    }

    // 心跳：每 2 分钟检查一次，服务端按 1 分钟去重
    setInterval(() => push(false), 120000);
    push(true);
    setTimeout(showMessage, 1200);

    window.SYNC = { push: () => push(true), authed: () => authed };
  })();
})();
