# -*- coding: utf-8 -*-
"""同舟共济服务端验收（登录 / 同步 / 权限 / AI 代理 / 限速）。

守四条：
1. 未登录与越权必须被挡（她的账号看不到后台）；
2. 密码用 scrypt 加盐哈希，明文不落盘；
3. AI 的 Key 只在服务端，接口不回显；
4. 登录有限速，单一密码的系统不防爆破等于没锁。

跑法：
  1) node server/set-password.js user  testpass123
  2) node server/set-password.js admin adminpass123
  3) node server/index.js
  4) python scripts/test_server.py
"""
import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get('SAT_SERVER', 'http://127.0.0.1:8848')
fails, checks = [], 0


def check(name, ok, detail=''):
    global checks
    checks += 1
    print(f'[{"PASS" if ok else "FAIL"}] {name} {detail}')
    if not ok:
        fails.append(name)


def req(method, path, body=None, cookie=None):
    """返回 (status, json, set_cookie)"""
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header('Content-Type', 'application/json')
    if cookie:
        r.add_header('Cookie', cookie)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw or '{}'), resp.headers.get('Set-Cookie')
            except json.JSONDecodeError:
                return resp.status, raw, resp.headers.get('Set-Cookie')
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw or '{}'), e.headers.get('Set-Cookie')
        except json.JSONDecodeError:
            return e.code, raw, e.headers.get('Set-Cookie')


def cookie_of(set_cookie):
    return (set_cookie or '').split(';')[0]


# ---------- 1. 未登录 / 越权 ----------
st, _, _ = req('GET', '/api/admin/overview')
check('未登录访问后台被拒', st == 403, str(st))

st, _, _ = req('GET', '/api/progress')
check('未登录读学习数据被拒', st == 401, str(st))

st, _, _ = req('POST', '/api/login', {'role': 'user', 'password': 'definitely-wrong'})
check('密码错误被拒', st == 401, str(st))

# ---------- 2. 登录 ----------
st, body, sc = req('POST', '/api/login', {'role': 'user', 'password': 'testpass123'})
check('她的密码可登录', st == 200 and body.get('role') == 'user', str(st))
user_ck = cookie_of(sc)
check('会话用 HttpOnly Cookie', 'HttpOnly' in (sc or ''), (sc or '')[:40])
check('会话带 SameSite', 'SameSite=Lax' in (sc or ''))

st, body, sc2 = req('POST', '/api/login', {'role': 'admin', 'password': 'adminpass123'})
check('管理密码可登录', st == 200 and body.get('role') == 'admin', str(st))
admin_ck = cookie_of(sc2)

# ---------- 3. 越权：她的账号进不了后台 ----------
st, _, _ = req('GET', '/api/admin/overview', cookie=user_ck)
check('她的账号访问后台被拒', st == 403, str(st))

st, _, _ = req('PUT', '/api/admin/ai', {'url': 'x'}, cookie=user_ck)
check('她的账号改不了 AI 配置', st == 403, str(st))

# ---------- 4. 学习数据同步 ----------
demo = {'answered': 120, 'correct': 78, 'streak': 9, 'wrongCount': 42, 'essayCount': 3,
        'byMod': {'资料分析': {'answered': 40, 'correct': 18},
                  '常识判断': {'answered': 30, 'correct': 26}}}
st, body, _ = req('PUT', '/api/progress', demo, cookie=user_ck)
check('可上传学习数据', st == 200 and body.get('ok'), str(st))

st, ov, _ = req('GET', '/api/admin/overview', cookie=admin_ck)
check('后台看得到题量', ov.get('total') == 120, str(ov.get('total')))
check('后台算得出正确率', ov.get('accuracy') == 65, str(ov.get('accuracy')))
check('后台看得到连续天数', ov.get('streak') == 9, str(ov.get('streak')))
mods = ov.get('modules') or []
check('后台按正确率升序列出模块',
      [m['mod'] for m in mods] == ['资料分析', '常识判断'], str(mods))

# ---------- 5. AI 配置：Key 不回显 ----------
st, _, _ = req('PUT', '/api/admin/ai',
               {'url': 'https://api.deepseek.com/v1/chat/completions',
                'model': 'deepseek-chat', 'key': 'sk-secret-should-not-leak'}, cookie=admin_ck)
check('管理员可保存 AI 配置', st == 200, str(st))

st, ai, _ = req('GET', '/api/admin/ai', cookie=admin_ck)
check('读回配置不含 Key 本身', 'key' not in ai and ai.get('hasKey') is True, str(ai))
check('读回不含密钥明文', 'sk-secret' not in json.dumps(ai, ensure_ascii=False), str(ai)[:80])
check('接口地址与模型可读回',
      ai.get('model') == 'deepseek-chat' and 'deepseek.com' in (ai.get('url') or ''), str(ai))

# 磁盘上也不能有明文
dbp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server', 'data', 'db.json')
if os.path.exists(dbp):
    raw = open(dbp, encoding='utf-8').read()
    check('磁盘上无密码明文', 'testpass123' not in raw and 'adminpass123' not in raw)
    check('磁盘上密码是加盐哈希', '"salt"' in raw and '"hash"' in raw)
    check('磁盘上有 AI Key（本就该存服务端）', 'sk-secret-should-not-leak' in raw)

# ---------- 6. 留言 ----------
st, _, _ = req('PUT', '/api/message', {'text': '今天也一起'}, cookie=admin_ck)
check('管理员可写留言', st == 200, str(st))
st, m, _ = req('GET', '/api/message', cookie=user_ck)
check('她读得到留言', m.get('text') == '今天也一起', str(m))

# ---------- 7. 登出 ----------
st, _, sc3 = req('POST', '/api/logout', cookie=user_ck)
check('可登出且清 Cookie', st == 200 and 'Max-Age=0' in (sc3 or ''), str(st))
st, _, _ = req('GET', '/api/progress', cookie=user_ck)
check('登出后会话失效', st == 401, str(st))

# ---------- 8. 登录限速 ----------
codes = []
for _ in range(8):
    st, _, _ = req('POST', '/api/login', {'role': 'user', 'password': 'nope'})
    codes.append(st)
check('连续失败触发限速 429', 429 in codes, str(codes))

print(f'==== 服务端验收：通过 {checks - len(fails)}/{checks}，失败 {fails or "无"} ====')
raise SystemExit(1 if fails else 0)
