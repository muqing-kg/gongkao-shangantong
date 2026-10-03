/**
 * 同舟共济 · 服务端
 *
 * 为什么需要它：密码登录、后台看学情、集中配 AI Key —— 这三件事纯前端做不到
 * （前端 JS 是公开的，Key 下发到浏览器就等于公开）。
 *
 * 只干四件事：登录、学习数据同步、AI 代理、后台。
 * 题库和图片仍是静态资源，由本服务或 OpenResty 直接托管。
 *
 * 启动：node server/index.js
 * 环境变量：PORT（默认 8848）、DATA_DIR（默认 server/data）
 */
'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const url = require('url');

const PORT = Number(process.env.PORT || 8848);
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, 'data');
const ROOT = path.join(__dirname, '..');
const DB_FILE = path.join(DATA_DIR, 'db.json');
const SESSION_DAYS = 30;
const LOGIN_WINDOW_MS = 60 * 1000;   // 登录限速窗口
const LOGIN_MAX = 5;                 // 窗口内最多几次

fs.mkdirSync(DATA_DIR, { recursive: true });

/* ---------------- 极简 JSON 存储 ----------------
   单用户系统，一个 JSON 文件够用；备份就是复制文件。
   换成 SQLite 也很容易，接口不变。 */
function loadDb() {
  try { return JSON.parse(fs.readFileSync(DB_FILE, 'utf8')); }
  catch { return { users: {}, sessions: {}, progress: null, config: {}, messages: [], goals: {}, activity: [] }; }
}
function saveDb(db) {
  const tmp = DB_FILE + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(db, null, 2), 'utf8');
  fs.renameSync(tmp, DB_FILE);   // 原子写，避免写一半崩了把数据弄坏
}
let db = loadDb();

/* ---------------- 密码哈希 ----------------
   scrypt + 随机盐；明文永不落盘。 */
function hashPassword(pw, salt) {
  salt = salt || crypto.randomBytes(16).toString('hex');
  const hash = crypto.scryptSync(pw, salt, 32).toString('hex');
  return { salt, hash };
}
/* 环境变量优先：USER_PASSWORD / ADMIN_PASSWORD。
   在编排（docker-compose）里写一次就行，不用再跑脚本改 db.json。
   值在启动时哈希进内存，验证路径与数据库模式完全一致。 */
const ENV_PW = {};
for (const [role, key] of [['user', 'USER_PASSWORD'], ['admin', 'ADMIN_PASSWORD']]) {
  const v = process.env[key];
  if (v) ENV_PW[role] = hashPassword(v);
}
function userRecord(role) {
  return ENV_PW[role] || db.users[role];
}

function verifyPassword(pw, rec) {
  if (!rec || !rec.salt || !rec.hash) return false;
  const { hash } = hashPassword(pw, rec.salt);
  // 定长比较，避免计时侧信道
  return crypto.timingSafeEqual(Buffer.from(hash, 'hex'), Buffer.from(rec.hash, 'hex'));
}

/* ---------------- 会话 ---------------- */
function newSession(role) {
  const token = crypto.randomBytes(32).toString('hex');
  const expires = Date.now() + SESSION_DAYS * 86400e3;
  db.sessions[token] = { role, expires };
  // 顺手清掉过期会话
  for (const [k, v] of Object.entries(db.sessions)) if (v.expires < Date.now()) delete db.sessions[k];
  saveDb(db);
  return { token, expires };
}
function readSession(req) {
  const cookie = req.headers.cookie || '';
  const m = cookie.match(/(?:^|;\s*)sat_session=([a-f0-9]{64})/);
  if (!m) return null;
  const s = db.sessions[m[1]];
  if (!s || s.expires < Date.now()) return null;
  return { token: m[1], ...s };
}
function clearCookie() {
  return 'sat_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0';
}
function sessionCookie(token, expires) {
  const maxAge = Math.floor((expires - Date.now()) / 1000);
  return `sat_session=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}`;
}

/* ---------------- 登录限速 ---------------- */
const attempts = new Map();
function tooMany(ip) {
  const now = Date.now();
  const rec = (attempts.get(ip) || []).filter(t => now - t < LOGIN_WINDOW_MS);
  attempts.set(ip, rec);
  return rec.length >= LOGIN_MAX;
}
function noteAttempt(ip) {
  const rec = attempts.get(ip) || [];
  rec.push(Date.now());
  attempts.set(ip, rec);
}

/* ---------------- 工具 ---------------- */
const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
  '.gif': 'image/gif', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.jfif': 'image/jpeg',
};
function send(res, code, body, headers) {
  res.writeHead(code, Object.assign({ 'Cache-Control': 'no-store' }, headers || {}));
  res.end(body);
}
function sendJson(res, code, obj, headers) {
  send(res, code, JSON.stringify(obj), Object.assign({ 'Content-Type': 'application/json; charset=utf-8' }, headers || {}));
}
function readBody(req, limit = 8 * 1024 * 1024) {
  return new Promise((resolve, reject) => {
    let size = 0; const chunks = [];
    req.on('data', c => {
      size += c.length;
      if (size > limit) { reject(new Error('请求体过大')); req.destroy(); return; }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}
function clientIp(req) {
  return (req.headers['x-forwarded-for'] || '').split(',')[0].trim() || req.socket.remoteAddress || '?';
}

/* ---------------- 路由 ---------------- */
const server = http.createServer(async (req, res) => {
  const parsed = url.parse(req.url, true);
  const p = decodeURIComponent(parsed.pathname);
  const sess = readSession(req);

  try {
    /* ===== 登录 ===== */
    if (p === '/api/login' && req.method === 'POST') {
      const ip = clientIp(req);
      if (tooMany(ip)) return sendJson(res, 429, { error: '尝试过于频繁，请稍后再试' });
      noteAttempt(ip);

      const body = JSON.parse(await readBody(req) || '{}');
      const password = String(body.password || '');
      // 前端只传一个密码；这里自动判定身份。先试显式 role（兼容旧调用），再两个都试。
      let role = null;
      const order = body.role === 'admin' ? ['admin', 'user']
                  : body.role === 'user' ? ['user', 'admin']
                  : ['admin', 'user'];
      for (const r of order) {
        const rec = userRecord(r);
        if (rec && verifyPassword(password, rec)) { role = r; break; }
      }
      if (!role) {
        if (!userRecord('user') && !userRecord('admin')) {
          return sendJson(res, 400, { error: '还没设置密码，请在服务器上执行 node server/set-password.js' });
        }
        return sendJson(res, 401, { error: '密码不对' });
      }
      const s = newSession(role);
      if (db.users[role]) { db.users[role].lastLoginAt = Date.now(); saveDb(db); }
      return sendJson(res, 200, { ok: true, role, expires: s.expires },
        { 'Set-Cookie': sessionCookie(s.token, s.expires) });
    }

    if (p === '/api/logout' && req.method === 'POST') {
      if (sess) { delete db.sessions[sess.token]; saveDb(db); }
      return sendJson(res, 200, { ok: true }, { 'Set-Cookie': clearCookie() });
    }

    if (p === '/api/me') {
      if (!sess) return sendJson(res, 401, { error: '未登录' });
      return sendJson(res, 200, { role: sess.role });
    }

    /* ===== 学习数据同步（她的端） ===== */
    if (p === '/api/progress') {
      if (!sess) return sendJson(res, 401, { error: '未登录' });
      if (req.method === 'GET') return sendJson(res, 200, db.progress || {});
      if (req.method === 'PUT') {
        if (sess.role !== 'user' && sess.role !== 'admin') return sendJson(res, 403, { error: '无权' });
        const incoming = JSON.parse(await readBody(req) || '{}');
        // 记录活跃轨迹：首次同步与每次心跳都留痕，供后台看「什么时候在学」
        db.activity = db.activity || [];
        db.activity.push({ at: Date.now(), answered: Number(incoming.answered) || 0 });
        if (db.activity.length > 2000) db.activity = db.activity.slice(-2000);
        db.progress = incoming;
        db.progress.updatedAt = Date.now();
        db.progress.lastActiveAt = Date.now();
        saveDb(db);
        return sendJson(res, 200, { ok: true, updatedAt: db.progress.updatedAt });
      }
    }

    /* ===== 留言（主人写给她的） ===== */
    if (p === '/api/message') {
      if (req.method === 'GET') {
        if (!sess) return sendJson(res, 401, { error: '未登录' });
        const list = db.messages || [];
        // 兼容旧字段：text 仍返回最后一条
        return sendJson(res, 200, {
          messages: list,
          text: (list[list.length - 1] || {}).text || '',
        });
      }
      if (req.method === 'POST' || req.method === 'PUT') {
        if (!sess || sess.role !== 'admin') return sendJson(res, 403, { error: '仅管理员' });
        const { text } = JSON.parse(await readBody(req) || '{}');
        const t = String(text || '').trim().slice(0, 200);
        if (!t) return sendJson(res, 400, { error: '内容不能为空' });
        const item = { id: crypto.randomBytes(6).toString('hex'), text: t, at: Date.now() };
        db.messages = db.messages || [];
        db.messages.push(item);
        saveDb(db);
        return sendJson(res, 200, { ok: true, item });
      }
      if (req.method === 'DELETE') {
        if (!sess || sess.role !== 'admin') return sendJson(res, 403, { error: '仅管理员' });
        const id = parsed.query.id || '';
        const before = (db.messages || []).length;
        db.messages = (db.messages || []).filter(m => m.id !== id);
        saveDb(db);
        return sendJson(res, 200, { ok: true, removed: before - db.messages.length });
      }
    }

    /* ===== AI 状态：学习端靠这个判断「能不能用」 ===== */
    if (p === '/api/ai/status') {
      if (!sess) return sendJson(res, 401, { error: '未登录' });
      const c = db.config.ai || {};
      return sendJson(res, 200, {
        configured: !!(c.url && c.key),
        model: c.model || '',
      });
    }

    /* ===== AI 代理：Key 只在服务端 ===== */
    if (p === '/api/ai' && req.method === 'POST') {
      if (!sess) return sendJson(res, 401, { error: '未登录' });
      const cfg = db.config.ai || {};
      if (!cfg.url || !cfg.key) return sendJson(res, 503, { error: 'AI 还没配置，请让管理员在后台填一下' });
      let payload = {};
      try { payload = JSON.parse(await readBody(req) || '{}'); } catch (_) {}
      // 模型名以服务端配置为准：学习端不知道管理员填的是哪个
      if (cfg.model) payload.model = cfg.model;
      const upstream = await fetch(cfg.url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${cfg.key}` },
        body: JSON.stringify(payload),
      });
      const text = await upstream.text();
      return send(res, upstream.status, text, { 'Content-Type': 'application/json; charset=utf-8' });
    }

    /* ===== 后台（仅管理员） ===== */
    if (p === '/api/admin/overview') {
      if (!sess || sess.role !== 'admin') return sendJson(res, 403, { error: '仅管理员' });
      const pr = db.progress || {};
      const byMod = pr.byMod || {};
      const rows = Object.entries(byMod).map(([mod, s]) => ({
        mod, n: s.answered || 0, acc: s.answered ? Math.round((s.correct || 0) / s.answered * 100) : 0,
      })).sort((a, b) => a.acc - b.acc);
      return sendJson(res, 200, {
        updatedAt: pr.updatedAt || 0,
        total: pr.answered || 0,
        correct: pr.correct || 0,
        accuracy: pr.answered ? Math.round((pr.correct || 0) / pr.answered * 100) : 0,
        streak: pr.streak || 0,
        daily: (pr.daily || []).slice(-30),
        modules: rows,
        wrongs: pr.wrongCount || 0,
        essays: pr.essayCount || 0,
        goal: db.goals || {},
      });
    }

    if (p === '/api/admin/activity') {
      if (!sess || sess.role !== 'admin') return sendJson(res, 403, { error: '仅管理员' });
      const pr = db.progress || {};
      const daily = (pr.daily || []).slice(-30);
      // 把活跃轨迹按天聚合，得出「每天在哪些时段用过」
      const byDay = {};
      for (const a of (db.activity || [])) {
        const d = new Date(a.at);
        const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
        (byDay[key] = byDay[key] || []).push(a.at);
      }
      const days = Object.entries(byDay).map(([date, ats]) => {
        ats.sort((x, y) => x - y);
        const rec = daily.find(d => d.date === date) || {};
        // 相邻两次心跳间隔 <= 5 分钟算连续学习
        let sec = 0;
        for (let i = 1; i < ats.length; i++) {
          const gap = (ats[i] - ats[i - 1]) / 1000;
          if (gap <= 300) sec += gap;
        }
        return {
          date,
          visits: ats.length,
          firstAt: ats[0],
          lastAt: ats[ats.length - 1],
          minutes: Math.round(sec / 60),
          answered: Number(rec.answered) || 0,
          correct: Number(rec.correct) || 0,
        };
      }).sort((a, b) => b.date.localeCompare(a.date));
      return sendJson(res, 200, {
        lastActiveAt: pr.lastActiveAt || pr.updatedAt || 0,
        lastLoginAt: Math.max(db.users?.user?.lastLoginAt || 0, db.users?.admin?.lastLoginAt || 0),
        days,
        totalMinutes: days.reduce((n, d) => n + d.minutes, 0),
      });
    }

    if (p === '/api/admin/ai') {
      if (!sess || sess.role !== 'admin') return sendJson(res, 403, { error: '仅管理员' });
      if (req.method === 'GET') {
        const c = db.config.ai || {};
        // 只回显地址与模型，Key 不回显
        return sendJson(res, 200, { url: c.url || '', model: c.model || '', hasKey: !!c.key });
      }
      if (req.method === 'PUT') {
        const b = JSON.parse(await readBody(req) || '{}');
        db.config.ai = {
          url: String(b.url || '').trim(),
          model: String(b.model || '').trim(),
          key: b.key ? String(b.key).trim() : (db.config.ai?.key || ''),
        };
        saveDb(db);
        return sendJson(res, 200, { ok: true });
      }
    }

    if (p === '/api/admin/models') {
      if (!sess || sess.role !== 'admin') return sendJson(res, 403, { error: '仅管理员' });
      const c = db.config.ai || {};
      if (!c.url || !c.key) return sendJson(res, 400, { error: '先填接口地址和 Key' });
      // 由 chat/completions 推出 /models
      const base = c.url.replace(/\/chat\/completions\/?$/, '');
      const mUrl = /\/chat\/completions\/?$/.test(c.url) ? base + '/models' : c.url.replace(/\/?$/, '') + '/models';
      try {
        const r = await fetch(mUrl, { headers: { Authorization: `Bearer ${c.key}` } });
        const txt = await r.text();
        if (!r.ok) return sendJson(res, 502, { error: `上游返回 ${r.status}`, detail: txt.slice(0, 200) });
        let data = {};
        try { data = JSON.parse(txt); } catch (_) { return sendJson(res, 502, { error: '上游返回的不是 JSON' }); }
        const list = (data.data || data.models || []).map(x => x.id || x.name || x).filter(Boolean);
        return sendJson(res, 200, { models: list });
      } catch (e) {
        return sendJson(res, 502, { error: '拉取失败：' + (e?.message || e) });
      }
    }

    if (p === '/api/admin/goal' && req.method === 'PUT') {
      if (!sess || sess.role !== 'admin') return sendJson(res, 403, { error: '仅管理员' });
      const b = JSON.parse(await readBody(req) || '{}');
      db.goals = { exam: String(b.exam || ''), date: String(b.date || ''), daily: Number(b.daily) || 0 };
      saveDb(db);
      return sendJson(res, 200, { ok: true });
    }

    /* ===== 静态资源 ===== */
    // 未登录时，受保护的页面一律送去登录页
    const PROTECTED = ['/', '/index.html', '/admin.html'];
    if (PROTECTED.includes(p)) {
      if (!sess) return send(res, 302, '', { Location: '/login.html' });
      // 学习端不让进后台，管理端不让进学习页（各走各的）
      if (p === '/admin.html' && sess.role !== 'admin') return send(res, 302, '', { Location: '/index.html' });
      if (p !== '/admin.html' && sess.role === 'admin') return send(res, 302, '', { Location: '/admin.html' });
    }
    let file = p === '/' ? '/index.html' : p;
    // 防目录穿越
    const abs = path.normalize(path.join(ROOT, file));
    if (!abs.startsWith(ROOT)) return send(res, 403, 'Forbidden');
    if (!fs.existsSync(abs) || fs.statSync(abs).isDirectory()) return send(res, 404, 'Not Found');

    const ext = path.extname(abs).toLowerCase();
    const stat = fs.statSync(abs);
    // 图片强缓存；html 不缓存
    const cc = ext === '.html' ? 'no-cache'
      : ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.jfif'].includes(ext) ? 'public, max-age=31536000, immutable'
      : 'public, max-age=300';
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream', 'Cache-Control': cc, 'Content-Length': stat.size });
    fs.createReadStream(abs).pipe(res);
  } catch (e) {
    sendJson(res, 500, { error: e?.message || '服务器错误' });
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`同舟共济服务端已启动: http://127.0.0.1:${PORT}`);
  console.log(`数据目录: ${DATA_DIR}`);
  if (Object.keys(ENV_PW).length) {
    console.log(`密码来源: 环境变量（${Object.keys(ENV_PW).join(', ')}）`);
  }
  const hasUser = !!userRecord('user'), hasAdmin = !!userRecord('admin');
  if (!hasUser || !hasAdmin) {
    console.log('提示：还没设密码，执行');
    if (!hasUser) console.log('  node server/set-password.js user  <她的密码>');
    if (!hasAdmin) console.log('  node server/set-password.js admin <管理密码>');
  }
});
