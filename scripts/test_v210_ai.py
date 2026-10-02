# -*- coding: utf-8 -*-
"""致泽学堂 v2.10 AI 接入层与学情诊断验收。

不需要真实 API Key：用 Playwright 拦截 /chat/completions，验证
请求格式、发送内容、渲染与错误处理。

守四件事：
1. 配置存独立 localStorage，**不随学习数据备份泄露**；
2. 只发送学情统计数据，**不发送题目内容与答案**（硬约束）；
3. 请求是标准 OpenAI 兼容格式（URL / Authorization / model / messages）；
4. HTTP 错误被翻译成用户能照做的动作，而不是甩一个 401。
"""
import json
import os
from playwright.sync_api import sync_playwright

URL = os.environ.get('SAT_TEST_URL', 'http://127.0.0.1:8140/index.html')
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

FAKE_KEY = 'sk-test-should-never-leak-12345'
fails = []
checks = 0


def check(name, ok, detail=''):
    global checks
    checks += 1
    print(f'[{"PASS" if ok else "FAIL"}] {name} {detail}')
    if not ok:
        fails.append(name)


# 4 个模块 × 8 题；byMod 由 attempts 推出，保证与配速/错因口径一致
SEED = """
  const mk=(mod,dur,nOk,n,why)=>{ const out=[]; for(let i=0;i<n;i++)
    out.push({t:Date.now(),d:today(),qid:mod+i,mod,ok:i<nOk,src:'2024·省考',point:'工程问题',
              rate:60,dur,multi:false,type:'真题',txn:'',why:i<nOk?'':why}); return out; };
  const A=[...mk('资料分析',100,4,8,'来不及'),...mk('常识判断',25,7,8,''),
           ...mk('言语理解',45,6,8,'不会'),...mk('数量关系',110,3,8,'来不及')];
  store.attempts=A;
  const byMod={};
  A.forEach(a=>{ const b=byMod[a.mod]=byMod[a.mod]||{answered:0,correct:0}; b.answered++; if(a.ok) b.correct++; });
  store.stats={answered:A.length, correct:A.filter(a=>a.ok).length, byMod, daily:[]};
  store.plan={exam:'2026 省考',date:'2026-11-29',daily:60};
  save();
"""

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROME, headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))

    captured = {}
    mode = {'status': 200,
            'body': '{"choices":[{"message":{"content":"【最关键的 2 个问题】测试诊断输出。"}}]}'}

    def handle(route):
        captured['url'] = route.request.url
        captured['headers'] = route.request.headers
        captured['post'] = route.request.post_data
        route.fulfill(status=mode['status'], content_type='application/json', body=mode['body'])

    page.route('**/chat/completions', handle)

    mcap = {}
    mmode = {'status': 200,
             'body': '{"data":[{"id":"deepseek-v4-pro"},{"id":"deepseek-flash"},{"id":"deepseek-flash"}]}'}

    def handle_models(route):
        mcap['url'] = route.request.url
        mcap['headers'] = route.request.headers
        route.fulfill(status=mmode['status'], content_type='application/json', body=mmode['body'])

    page.route('**/models', handle_models)
    page.goto(URL, wait_until='domcontentloaded', timeout=120000)

    # ---------- 0. 先造学情数据（无数据时能力分析页会早返回） ----------
    page.evaluate("() => {" + SEED + "}")

    # ---------- 1. AI 模块与配置页 ----------
    check('AI 接入层已加载', page.evaluate('() => !!(window.AI && window.AI.chat)'))
    page.evaluate("switchTab('more')")
    page.wait_for_timeout(300)
    check('设置页出现 AI 接入卡', 'AI 接入' in page.locator('#view').inner_text())
    check('接口地址/模型/Key 三个输入框就位',
          page.locator('#aiUrl').count() == 1 and page.locator('#aiModel').count() == 1
          and page.locator('#aiKey').count() == 1)
    check('Key 用密码框输入', page.get_attribute('#aiKey', 'type') == 'password')

    # ---------- 2. 未配置时的引导 ----------
    page.evaluate("switchTab('growth'); openGrowthTool('ability')")
    page.wait_for_timeout(300)
    check('未配置时能力分析页给出配置引导',
          '去配置' in page.locator('#view').inner_text(),
          page.locator('#view').inner_text()[:120])

    # ---------- 3. 保存配置，Key 不进备份 ----------
    page.evaluate("switchTab('more')")
    page.wait_for_timeout(250)
    page.fill('#aiUrl', 'https://api.deepseek.com/v1/chat/completions')
    page.fill('#aiModel', 'deepseek-flash')
    page.fill('#aiKey', FAKE_KEY)
    page.click('button:has-text("保存")')
    page.wait_for_timeout(250)
    cfg = page.evaluate("() => JSON.parse(localStorage.getItem('zhize_ai_cfg_v1'))")
    check('配置写入独立 localStorage',
          cfg.get('model') == 'deepseek-flash' and cfg.get('key') == FAKE_KEY, str(cfg.get('model')))
    check('Key 不随学习数据泄露',
          FAKE_KEY not in page.evaluate('() => JSON.stringify(store)'))
    keys = page.evaluate("() => Object.keys(localStorage)")
    check('学习数据与 AI 配置分属两个存储键',
          'shangan_tong_v1' in keys and 'zhize_ai_cfg_v1' in keys, str(keys))

    # ---------- 4. 学情快照不含题目内容 ----------
    snap = page.evaluate("() => {" + SEED + """
      const s = studySnapshot();
      return {keys:Object.keys(s).sort(), prompt:aiDiagPrompt(s), mods:s.mods.length,
              pace:s.pace.length, why:s.why.length};
    }""")
    check('快照字段固定为统计量',
          snap['keys'] == ['avgDur', 'dailyTarget', 'date', 'daysLeft', 'exam', 'mods',
                           'overallAcc', 'pace', 'streak', 'todayDone', 'totalAnswered',
                           'weakPoints', 'why'], str(snap['keys']))
    check('快照含 4 个模块', snap['mods'] == 4, str(snap['mods']))
    check('快照含配速与错因', snap['pace'] == 4 and snap['why'] >= 1,
          f"pace={snap['pace']} why={snap['why']}")
    pr = snap['prompt']
    check('prompt 含模块表现', '【模块表现】' in pr and '资料分析' in pr)
    check('prompt 含配速与错因', '【配速诊断】' in pr and '【错因分布】' in pr)
    check('prompt 含目标与天数', '2026 省考' in pr and '距今' in pr)
    check('prompt 不含题干/答案字段',
          '题干' not in pr and 'analysis' not in pr and 'options' not in pr and 'answer' not in pr)

    # ---------- 5. 发起诊断：请求格式 ----------
    page.evaluate("switchTab('growth'); openGrowthTool('ability')")
    page.wait_for_timeout(300)
    check('配置后出现诊断按钮', '让 AI 读一遍' in page.locator('#view').inner_text(),
          page.locator('#view').inner_text()[:120])
    page.click('button:has-text("让 AI 读一遍")')
    page.wait_for_timeout(1500)
    check('请求发到配置的地址',
          captured.get('url') == 'https://api.deepseek.com/v1/chat/completions', str(captured.get('url')))
    check('带 Bearer 鉴权头',
          captured.get('headers', {}).get('authorization') == 'Bearer ' + FAKE_KEY)
    body = json.loads(captured.get('post') or '{}')
    check('模型名正确', body.get('model') == 'deepseek-flash', str(body.get('model')))
    check('messages 为 system+user 两条',
          [m['role'] for m in body.get('messages', [])] == ['system', 'user'],
          str([m['role'] for m in body.get('messages', [])]))
    check('system 约束了不编造与不泄答案',
          '不要编造' in body['messages'][0]['content']
          and '不要给出任何题目的答案' in body['messages'][0]['content'])
    check('user 内容为学情数据', '【模块表现】' in body['messages'][1]['content'])
    check('不发送 stream', body.get('stream') is False)

    # ---------- 6. 渲染结果 ----------
    txt = page.locator('#view').inner_text()
    check('渲染 AI 诊断结果', '测试诊断输出' in txt, txt[:120])
    check('标注 AI 生成仅供参考', 'AI 生成' in txt and '仅供参考' in txt)

    # ---------- 7. 错误处理 ----------
    for status, expect in [(401, '鉴权失败'), (404, '接口地址'), (429, '频繁'), (500, '服务端')]:
        mode['status'] = status
        mode['body'] = '{"error":"boom"}'
        page.evaluate("aiClearResult('diag'); aiErrors.diag=''; renderAnalysis();")
        page.wait_for_timeout(250)
        page.click('button:has-text("让 AI 读一遍")')
        page.wait_for_timeout(1000)
        t = page.locator('#view').inner_text()
        check(f'{status} 错误文案可照做', expect in t, t[:100])

    # 连不上：用 route.abort 确定性地模拟网络层失败
    # （不能靠不存在的域名——本机有 Clash 代理时会返回 502 而不是 DNS 失败）
    mode['status'] = 200
    page.unroute('**/chat/completions')
    page.route('**/chat/completions', lambda route: route.abort('failed'))
    page.evaluate("AI.saveCfg({url:'https://api.deepseek.com/v1/chat/completions'})")
    page.evaluate("aiClearResult('diag'); aiErrors.diag=''; renderAnalysis();")
    page.wait_for_timeout(250)
    page.click('button:has-text("让 AI 读一遍")')
    page.wait_for_timeout(2500)
    t = page.locator('#view').inner_text()
    check('连不上时给出可读提示', '连不上' in t, t[:120])

    # ---------- 8. 数据太少时拒绝调用 ----------
    # 保留少量 attempts，否则 renderAnalysis 会早返回、按钮根本不出现
    page.evaluate("""() => {
      AI.saveCfg({url:'https://api.deepseek.com/v1/chat/completions', key:'sk-x'});
      const A=[];
      for(let i=0;i<5;i++) A.push({t:Date.now(),d:today(),qid:'few'+i,mod:'常识判断',ok:false,
        src:'',point:'',rate:60,dur:30,multi:false,type:'',txn:'',why:''});
      store.attempts=A;
      store.stats={answered:5,correct:0,byMod:{'常识判断':{answered:5,correct:0}},daily:[]};
      save();
      aiClearResult('diag'); aiErrors.diag=''; renderAnalysis();
    }""")
    page.wait_for_timeout(300)
    check('数据太少时仍显示诊断按钮', '让 AI 读一遍' in page.locator('#view').inner_text())
    captured.clear()
    page.click('button:has-text("让 AI 读一遍")')
    page.wait_for_timeout(800)
    check('数据太少时不发起请求', captured.get('url') is None, str(captured.get('url')))

    # ---------- 9. 获取模型列表（不手输模型名） ----------
    page.evaluate("""() => {
      AI.saveCfg({url:'https://api.deepseek.com/v1/chat/completions', model:'', key:'sk-x'});
      switchTab('more');
    }""")
    page.wait_for_timeout(300)
    check('配置页有「获取模型列表」按钮', page.locator('#aiModelsBtn').count() == 1)
    check('下拉框初始隐藏', page.locator('#aiModelPick.hidden').count() == 1)

    page.click('#aiModelsBtn')
    page.wait_for_timeout(1000)
    check('模型列表请求地址由对话地址推出',
          mcap.get('url') == 'https://api.deepseek.com/v1/models', str(mcap.get('url')))
    check('模型列表带鉴权头',
          mcap.get('headers', {}).get('authorization') == 'Bearer sk-x')
    check('下拉框显示出来', page.locator('#aiModelPick:not(.hidden)').count() == 1)
    opts = page.evaluate("() => [...document.querySelectorAll('#aiModelPick option')].map(o => o.value)")
    check('选项去重且排序', opts == ['', 'deepseek-flash', 'deepseek-v4-pro'], str(opts))

    page.select_option('#aiModelPick', 'deepseek-v4-pro')
    page.wait_for_timeout(350)
    check('选择后写回模型输入框', page.input_value('#aiModel') == 'deepseek-v4-pro',
          page.input_value('#aiModel'))
    check('选择后即保存到配置',
          page.evaluate("() => JSON.parse(localStorage.getItem('zhize_ai_cfg_v1')).model") == 'deepseek-v4-pro')

    # 获取失败要给出可照做的提示
    mmode['status'] = 401
    mmode['body'] = '{"error":"bad key"}'
    page.click('#aiModelsBtn')
    page.wait_for_timeout(1000)
    check('获取失败时提示鉴权问题',
          '鉴权失败' in page.locator('#toast').inner_text(), page.locator('#toast').inner_text())
    check('失败后按钮恢复可用',
          page.locator('#aiModelsBtn').is_enabled() and page.locator('#aiModelsBtn').inner_text() == '获取模型列表',
          page.locator('#aiModelsBtn').inner_text())

    # ---------- 10. AI 排计划 + 结果持久化 ----------
    page.unroute('**/chat/completions')
    page.route('**/chat/completions', handle)
    mode['status'] = 200
    mode['body'] = ('{"choices":[{"message":{"content":'
                    '"第 1 天：资料分析 · 20 题 · 提速 · 30 分钟\\n【本周重点】资料分析提速"}}]}')
    page.evaluate("() => {" + SEED + """
      AI.saveCfg({url:'https://api.deepseek.com/v1/chat/completions', model:'deepseek-flash', key:'sk-x'});
      switchTab('growth'); openGrowthTool('plan');
    }""")
    page.wait_for_timeout(300)
    check('学习计划页出现 AI 排计划卡', 'AI 排计划' in page.locator('#view').inner_text(),
          page.locator('#view').inner_text()[-200:])
    captured.clear()
    page.click('button:has-text("让 AI 排 7 天计划")')
    page.wait_for_timeout(1800)
    body = json.loads(captured.get('post') or '{}')
    check('计划请求用计划版 system',
          '排接下来 7 天' in body.get('messages', [{}])[0].get('content', ''),
          str(body.get('messages', [{}])[0].get('content', ''))[:60])
    check('计划 user 复用同一份学情快照',
          '【模块表现】' in body.get('messages', [{}, {}])[1].get('content', ''))
    check('计划结果渲染', '第 1 天' in page.locator('#view').inner_text())
    check('计划结果落盘', page.evaluate("() => (aiText('plan')||'').includes('第 1 天')"))
    check('计划结果与学习数据分开存',
          page.evaluate("() => !!localStorage.getItem('zhize_ai_results_v1')")
          and page.evaluate("() => !JSON.stringify(store).includes('第 1 天')"))

    # 刷新后仍在
    page.reload(wait_until='domcontentloaded', timeout=120000)
    page.evaluate("switchTab('growth'); openGrowthTool('plan')")
    page.wait_for_timeout(300)
    check('刷新后计划仍在', '第 1 天' in page.locator('#view').inner_text())

    # 清除
    page.click('button:has-text("清除")')
    page.wait_for_timeout(350)
    check('清除后计划消失', '第 1 天' not in page.locator('#view').inner_text())
    check('清除后回到待触发态', '让 AI 排 7 天计划' in page.locator('#view').inner_text())

    # ---------- 11. 配置搬运（主人配好，导出给他人粘贴导入） ----------
    page.evaluate("""() => {
      AI.saveCfg({url:'https://api.deepseek.com/v1/chat/completions', model:'deepseek-flash', key:'sk-carry-1'});
      switchTab('more');
    }""")
    page.wait_for_timeout(300)
    check('配置页有导入与复制按钮',
          page.locator('button:has-text("导入配置")').count() == 1
          and page.locator('button:has-text("复制我的配置")').count() == 1)
    blob = page.evaluate("() => AI.exportCfg()")
    check('导出内容带识别前缀', blob.startswith('ZSAI1:'), blob[:24])
    check('导出内容不含明文 Key', 'sk-carry-1' not in blob)

    page.evaluate("AI.saveCfg({url:'https://x.invalid/v1/chat/completions', model:'other', key:'sk-other'})")
    page.fill('#aiImport', blob)
    page.click('button:has-text("导入配置")')
    page.wait_for_timeout(450)
    back = page.evaluate("() => AI.loadCfg()")
    check('导入后配置完整还原',
          back['url'] == 'https://api.deepseek.com/v1/chat/completions'
          and back['model'] == 'deepseek-flash' and back['key'] == 'sk-carry-1', str(back))

    page.fill('#aiImport', '这不是一段配置')
    page.click('button:has-text("导入配置")')
    page.wait_for_timeout(450)
    check('导入非法内容给出可读提示',
          '无法识别' in page.locator('#toast').inner_text(), page.locator('#toast').inner_text())

    page.fill('#aiImport', 'ZSAI1:eyJ1cmwiOiIifQ==')   # {"url":""}
    page.click('button:has-text("导入配置")')
    page.wait_for_timeout(450)
    check('导入缺少地址的配置被拒绝',
          '没有接口地址' in page.locator('#toast').inner_text(), page.locator('#toast').inner_text())

    check('无 JS 运行错误', not errors, str(errors[:3]))
    browser.close()

print(f'==== v2.10 AI 接入验收：通过 {checks - len(fails)}/{checks}，失败 {fails or "无"} ====')
raise SystemExit(1 if fails else 0)
