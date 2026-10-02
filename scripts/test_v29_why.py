# -*- coding: utf-8 -*-
"""致泽学堂 v2.9 错因标注验收。

针对「正确率上不去」：错分三种，对策完全不同——
不会→补知识点，来不及→练取舍，粗心→练审题，蒙的→打基础。
不标注就分不清，等于把三个病当一个病治。

守四件事：
1. 只在逐题回顾里、只对错题/未作答出标注按钮；
2. 标注写进 attempts[].why，再点一次取消；
3. 标注够 5 条才出「失分结构」卡，占比与结论匹配最多的错因；
4. 导入脏数据时 why 被过滤，旧备份（无 why 字段）不报错。
"""
import json
import os
from playwright.sync_api import sync_playwright

URL = os.environ.get('SAT_TEST_URL', 'http://127.0.0.1:8140/index.html')
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

fails = []
checks = 0


def check(name, ok, detail=''):
    global checks
    checks += 1
    print(f'[{"PASS" if ok else "FAIL"}] {name} {detail}')
    if not ok:
        fails.append(name)


QUIZ = """() => {
  const qs=[
    {id:'w1',mod:'常识判断',type:'单选',stem:'测试题一',options:['甲','乙','丙','丁'],answer:0,analysis:'解析一'},
    {id:'w2',mod:'言语理解',type:'单选',stem:'测试题二',options:['甲','乙','丙','丁'],answer:1,analysis:'解析二'}
  ];
  startQuiz(qs,'错因测试');
  pick(1); nextQ();      // 第1题答错（正确是 A）
  pick(0); nextQ();      // 第2题答错（正确是 B），最后一题自动交卷
}"""

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROME, headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(URL, wait_until='domcontentloaded', timeout=120000)
    # 题库加载完成时若停在首页会自动 renderDash()，会覆盖直接渲染的视图；先等题库就绪以消除该竞态
    page.wait_for_function(
        "() => window.LAZY_BANK_STATUS && window.LAZY_BANK_STATUS.loaded", timeout=120000)

    # ---------- 1. 交卷结果页提示标注 ----------
    page.evaluate(QUIZ)
    page.wait_for_timeout(400)
    check('交卷后结果页出现', page.locator('#resultLayer:not(.hidden)').count() == 1)
    check('结果页提示标注错因', '标一下错因' in page.locator('#resultBox').inner_text(),
          page.locator('#resultBox').inner_text()[:120])

    # ---------- 2. 逐题回顾里只对错题出按钮 ----------
    page.evaluate("reviewQuiz()")
    page.wait_for_timeout(300)
    check('回顾页出现错因按钮组', page.locator('.why-box').count() == 1)
    chips = page.locator('.why-chip')
    check('四个错因按钮齐全', chips.count() == 4,
          str([chips.nth(i).inner_text() for i in range(chips.count())]))
    check('初始未标注', '未标注' in page.locator('.why-box').inner_text())

    # ---------- 3. 标注与取消 ----------
    page.click('.why-chip:has-text("来不及")')
    page.wait_for_timeout(250)
    check('标注写入 attempts[].why',
          page.evaluate("() => whyOf('w1')") == '来不及',
          page.evaluate("() => whyOf('w1')"))
    check('按钮变为选中态', page.locator('.why-chip.on').count() == 1)
    check('文案显示已标注', '已标注' in page.locator('.why-box').inner_text())

    page.click('.why-chip:has-text("来不及")')
    page.wait_for_timeout(250)
    check('再点一次取消标注', page.evaluate("() => whyOf('w1')") == '',
          page.evaluate("() => whyOf('w1')"))
    check('取消后无选中按钮', page.locator('.why-chip.on').count() == 0)

    page.click('.why-chip:has-text("粗心")')
    page.wait_for_timeout(250)
    check('可改标为其它错因', page.evaluate("() => whyOf('w1')") == '粗心')

    # 答对的题不出错因框
    page.evaluate('''() => {
      const qs=[{id:'ok1',mod:'常识判断',type:'单选',stem:'对题',options:['甲','乙','丙','丁'],answer:0,analysis:'解析'}];
      startQuiz(qs,'全对测试'); pick(0); nextQ();
    }''')
    page.wait_for_timeout(300)
    page.evaluate("reviewQuiz()")
    page.wait_for_timeout(300)
    check('答对的题不出错因按钮', page.locator('.why-box').count() == 0)

    # ---------- 4. 失分结构卡 ----------
    page.evaluate('''() => { store.attempts=[]; save(); renderAnalysis(); }''')
    page.wait_for_timeout(200)
    check('标注不足 5 条时不显示失分结构',
          '失分结构' not in page.locator('#view').inner_text())

    stats = page.evaluate('''() => {
      const mk=(why,n)=>{ const out=[]; for(let i=0;i<n;i++)
        out.push({t:Date.now(),d:today(),qid:why+i,mod:'常识判断',ok:false,src:'',point:'',
                  rate:60,dur:40,multi:false,type:'',txn:'',why}); return out; };
      store.attempts=[...mk('来不及',6),...mk('不会',3),...mk('粗心',1)];
      save();
      const s=whyStats();
      return {labeled:s.labeled, unlabeled:s.unlabeled, top:s.top.why,
              rows:s.rows.map(r=>({why:r.why,n:r.n,pct:r.pct}))};
    }''')
    check('已标注计数正确', stats['labeled'] == 10, str(stats))
    check('未标注计数正确', stats['unlabeled'] == 0, str(stats))
    check('占比计算正确',
          stats['rows'][0] == {'why': '来不及', 'n': 6, 'pct': 60}, str(stats['rows']))
    check('最多的错因识别正确', stats['top'] == '来不及', str(stats['top']))

    page.evaluate("renderAnalysis()")
    page.wait_for_timeout(300)
    txt = page.locator('#view').inner_text()
    check('能力分析页出现失分结构卡', '失分结构' in txt)
    check('显示错因占比', '来不及' in txt and '6 题 · 60%' in txt, txt[:200])
    check('给出对应建议（来不及→取舍）', '取舍问题' in txt and '配速诊断' in txt)

    # 换一个主导错因，建议要跟着换
    page.evaluate('''() => {
      const mk=(why,n)=>{ const out=[]; for(let i=0;i<n;i++)
        out.push({t:Date.now(),d:today(),qid:why+'x'+i,mod:'常识判断',ok:false,src:'',point:'',
                  rate:60,dur:40,multi:false,type:'',txn:'',why}); return out; };
      store.attempts=[...mk('粗心',5),...mk('不会',2)]; save(); renderAnalysis();
    }''')
    page.wait_for_timeout(250)
    check('主导错因变了建议跟着变', '审题问题' in page.locator('#view').inner_text())

    # ---------- 5. 数据边界 ----------
    norm = page.evaluate('''() => {
      const bad = normalizeStore({stats:{},wrongs:{},attempts:[
        {qid:'a',mod:'常识判断',why:'瞎写的'},{qid:'b',mod:'常识判断',why:'粗心'},
        {qid:'c',mod:'常识判断'}]}, true).attempts;
      return bad.map(a=>a.why);
    }''')
    check('非法 why 被过滤、合法保留、缺字段补空',
          norm == ['', '粗心', ''], str(norm))

    old = page.evaluate('''() => {
      const dump = JSON.parse(JSON.stringify(store));
      dump.attempts = dump.attempts.map(a => { delete a.why; return a; });
      return normalizeStore(dump, true).attempts.every(a => a.why === '');
    }''')
    check('旧备份（无 why 字段）可正常导入', old is True, str(old))

    # ---------- 6. AI 预判错因 ----------
    page.evaluate("AI.saveCfg({url:'https://api.deepseek.com/v1/chat/completions', model:'deepseek-flash', key:'sk-why'})")
    page.evaluate("""() => {
      const qs=[{id:'aiwhy1',mod:'资料分析',type:'真题',
                 stem:'以下不属于数字经济特征的是：',
                 options:['数据驱动','跨界融合','高耗能','平台化'],answer:2,
                 analysis:'考点：数字经济。数字经济特征是数据驱动、跨界融合、平台化，高耗能不是其特征。'}];
      startQuiz(qs,'AI错因测试'); pick(0); nextQ();   // 选 A，正确答案是 C
      reviewQuiz();
    }""")
    page.wait_for_timeout(400)
    check('配置 AI 后出现「让 AI 猜一下」', page.locator('button:has-text("让 AI 猜一下")').count() == 1)
    check('提示 AI 只给建议', '最终以你自己的判断为准' in page.locator('.why-box').inner_text())

    why_cap = {}
    wmode = {'body': '{"choices":[{"message":{"content":"粗心｜题干问的是“不属于”，你按“属于”选了。"}}]}'}

    def handle_why(route):
        why_cap['post'] = route.request.post_data
        route.fulfill(status=200, content_type='application/json', body=wmode['body'])

    page.route('**/chat/completions', handle_why)
    page.click('button:has-text("让 AI 猜一下")')
    page.wait_for_timeout(1200)
    wbody = json.loads(why_cap.get('post') or '{}')
    wsys = wbody['messages'][0]['content']
    wuser = wbody['messages'][1]['content']
    check('AI 错因 system 列出四个选项',
          all(w in wsys for w in ['不会', '来不及', '粗心', '蒙的']), wsys[:80])
    check('AI 错因 system 约束输出格式', '错因｜一句话理由' in wsys)
    check('AI 错因 user 带题干', '不属于数字经济特征' in wuser)
    check('AI 错因 user 带正确答案与我的答案',
          '正确答案：C' in wuser and '我的答案：A' in wuser, wuser[:300])
    check('AI 错因 user 带用时与平均用时', '这道题用时' in wuser and '平均每题用时' in wuser)
    check('AI 错因 user 带题库解析', '考点：数字经济' in wuser)
    check('AI 判断写回 why', page.evaluate("() => whyOf('aiwhy1')") == '粗心',
          page.evaluate("() => whyOf('aiwhy1')"))
    check('AI 判断结果提示出来', 'AI 判断：粗心' in page.locator('#toast').inner_text(),
          page.locator('#toast').inner_text())
    check('AI 猜完按钮恢复可用', page.locator('button:has-text("让 AI 猜一下")').is_enabled())

    # AI 返回无法识别的内容时不乱填
    page.evaluate("() => { const i=store.attempts.findIndex(a=>a.qid==='aiwhy1'); store.attempts[i].why=''; save(); renderReview(); }")
    page.wait_for_timeout(300)
    wmode['body'] = '{"choices":[{"message":{"content":"这题你大概是没看清吧。"}}]}'
    page.click('button:has-text("让 AI 猜一下")')
    page.wait_for_timeout(1200)
    check('AI 答非所问时不乱填错因', page.evaluate("() => whyOf('aiwhy1')") == '',
          page.evaluate("() => whyOf('aiwhy1')"))
    check('AI 答非所问时提示手动标注',
          '手动标注' in page.locator('#toast').inner_text(), page.locator('#toast').inner_text())

    # 答对的题不给 AI 按钮
    page.evaluate("""() => {
      const qs=[{id:'aiok1',mod:'常识判断',type:'单选',stem:'对题',options:['甲','乙','丙','丁'],answer:0,analysis:'解析'}];
      startQuiz(qs,'全对'); pick(0); nextQ(); reviewQuiz();
    }""")
    page.wait_for_timeout(400)
    check('答对的题没有 AI 猜错因按钮',
          page.locator('.why-box').count() == 0
          and page.locator('button:has-text("让 AI 猜一下")').count() == 0)

    check('无 JS 运行错误', not errors, str(errors[:3]))
    browser.close()

print(f'==== v2.9 错因标注验收：通过 {checks - len(fails)}/{checks}，失败 {fails or "无"} ====')
raise SystemExit(1 if fails else 0)
