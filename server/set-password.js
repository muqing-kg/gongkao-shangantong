/**
 * 设置密码（在她的端和管理端各设一个）
 *
 * 用法：
 *   node server/set-password.js user  <她的密码>
 *   node server/set-password.js admin <管理密码>
 *
 * 密码用 scrypt + 随机盐哈希后存进 server/data/db.json，明文不落盘、不进 Git。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, 'data');
const DB_FILE = path.join(DATA_DIR, 'db.json');

const role = process.argv[2];
const password = process.argv[3];

if (role !== 'user' && role !== 'admin') {
  console.error('用法: node server/set-password.js <user|admin> <密码>');
  process.exit(1);
}
if (!password || password.length < 6) {
  console.error('密码至少 6 位。单一密码的系统，密码就是唯一防线，请设强一点。');
  process.exit(1);
}

fs.mkdirSync(DATA_DIR, { recursive: true });
let db;
try { db = JSON.parse(fs.readFileSync(DB_FILE, 'utf8')); }
catch { db = { users: {}, sessions: {}, progress: null, config: {}, messages: [], goals: {} }; }
db.users = db.users || {};

const salt = crypto.randomBytes(16).toString('hex');
db.users[role] = { salt, hash: crypto.scryptSync(password, salt, 32).toString('hex'), at: Date.now() };

fs.writeFileSync(DB_FILE, JSON.stringify(db, null, 2), 'utf8');
console.log(`已设置 ${role === 'admin' ? '管理' : '她的'}密码（${password.length} 位，scrypt 加盐哈希）`);

if (db.users.user && db.users.admin) console.log('两个密码都已设置，可以启动了：node server/index.js');
else console.log('还差另一个角色的密码。');
